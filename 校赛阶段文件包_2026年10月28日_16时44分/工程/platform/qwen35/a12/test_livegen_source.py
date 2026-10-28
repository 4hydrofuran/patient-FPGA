"""Actual PC pidfd/flock/O_PATH and original BO policy tests; no Board calls."""
import argparse
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
from livegen_evidence import ROOT,OUT,read,save,sha
from livegen_source import Source,MutationInterlock,Capability
from livegen_platform import load_original,BoardPorts,interlocked_platform,inherited_lock_proof
from livegen_fixtures import FixturePorts,context_fixture,resident_fixture
from plm_page import Page
from plm_manager import ticks
from request_journal_verified import digest

def rejects(fn,expected=None):
    try:fn()
    except (RuntimeError,AssertionError,OSError,ValueError,KeyError,TypeError) as e:
        if expected is not None:assert expected in str(e),(expected,str(e))
        return str(e)
    raise AssertionError('expected refusal')

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a=p.parse_args();assert a.tag.isalnum();os.umask(0o077);results=[]
    build=read(ROOT/'evidence/model_pl_A/20261026-generation-binding-v1/BUILD-v3.json')
    def run(name,fn):
        with tempfile.TemporaryDirectory(prefix='a12-live-source-') as root:
            ports=FixturePorts(Path(root)/'source',time.monotonic_ns()+30_000_000_000)
            page=Page(build['writer_library'],build['writer_sha256']);events=[]
            worker=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            pidfd=os.pidfd_open(worker.pid);start=ticks(worker.pid);interlock=MutationInterlock()
            def revoke():events.append('revoke');page.revoke()
            source=Source(ports,interlock,revoke);source.attach_worker(worker,pidfd,start,page.snapshot)
            facts=context_fixture(worker.pid,start,ports.boot);route=resident_fixture(facts)
            try:
                fn(source,ports,page,worker,facts,route,events);results.append(dict(test=name,status='PASS_PC_ONLY'))
            finally:
                if worker.stdin and not worker.stdin.closed:worker.stdin.close()
                worker.wait(timeout=5)
                if source.pidfd is not None:os.close(source.pidfd);source.pidfd=None
                os.close(pidfd);ports.test_cleanup();page.close()
    def bind(source,page,facts):
        cap=source.issue(facts);ctx=digest(facts);page.bind(facts['worker_pid'],facts['worker_start_ticks'],ctx);source.consume(cap,ctx);page.load_end();return cap
    def normal(s,p,page,w,f,r,e):
        bind(s,page,f);s.seal_resident(r);page.revoke();w.stdin.close();w.wait(5);s.finish_native()
        assert s.normal_terminal and not s.blocked
        s.interlock.before('test restore',release_check=lambda:e.append('ORIGINAL_RELEASE_GATE_CALLED'))
        assert e[-2:]==['revoke','ORIGINAL_RELEASE_GATE_CALLED'] and s.interlock.retired
    run('full_bind_resident_terminal_and_fresh_release_order',normal)
    def same_uuid(s,p,page,w,f,r,e):
        bind(s,page,f);s.seal_resident(r);p.node.rename(p.node.with_name('old-device'));p.node.mkdir();p.attribute.write_text('PC_NO_DEVICE_SAME_UUID\n')
        p.base.observe();assert not p.base.blocked # earlier lease/JSON-only source misses this generation change
        rejects(s.observe,'generation node replaced/unloaded');assert s.blocked and page.snapshot()['revoked'] and e[-1]=='revoke'
    run('same_text_same_UUID_recreated_node_refuses_old_generation',same_uuid)
    for key,value in [('kernel_allowed',False),('memory',1114111),('cma',98303),('temp',55000),('closing',True),('skipped',True)]:
        def health(s,p,page,w,f,r,e,key=key,value=value):
            setattr(p,key,value);rejects(s.observe);assert s.blocked and e[-1]=='revoke' and page.snapshot()['revoked']
        run('health_'+key+'_refused',health)
    def expired(s,p,page,w,f,r,e):p.expires=time.monotonic_ns()-1;rejects(s.observe,'lease expired');assert s.blocked
    run('expired_original_lease_refused',expired)
    for field,value in [('xclbin_uuid','PC_WRONG_UUID'),('worker_start_ticks',1),('device_name','wrong'),('groups',[3]*5+[4]),('io_addresses',[0,0,49152,204800])]:
        def bad_context(s,p,page,w,f,r,e,field=field,value=value):
            f[field]=value;rejects(lambda:s.issue(f));assert s.blocked and page.snapshot()['revoked']
        run('context_'+field+'_refused',bad_context)
    for kind in ('JSON','copy','wrong_context','replay'):
        def bad_cap(s,p,page,w,f,r,e,kind=kind):
            cap=s.issue(f);ctx=digest(f)
            if kind=='replay':s.consume(cap,ctx);other=cap
            elif kind=='JSON':other={'issuer':s,'context_sha256':ctx,'epoch':cap.epoch}
            elif kind=='copy':other=Capability(s,ctx,cap.epoch,cap.mutation_serial,cap.observed_ns,cap.nonce)
            else:other=cap;ctx='f'*64
            rejects(lambda:s.consume(other,ctx),'foreign/replayed/stale');assert s.blocked and page.snapshot()['revoked']
        run('capability_'+kind+'_refused',bad_cap)
    for kind in ('count','sum','overlap','low2G','io_generation'):
        def bad_resident(s,p,page,w,f,r,e,kind=kind):
            bind(s,page,f)
            if kind=='count':r['a11_live_weights'].pop()
            elif kind=='sum':r['owned_bo_charged_bytes']-=8192
            elif kind=='overlap':r['a11_live_weights'][1]['addresses'][0]=r['a11_live_weights'][0]['addresses'][0]
            elif kind=='low2G':r['a11_live_weights'][-1]['addresses'][-1]=2147483648
            else:r['a11_io_bo_addresses']=list(r['a11_io_bo_addresses']);r['a11_io_bo_addresses'][0]=r['a11_live_weights'][0]['addresses'][0];r['a11_live_weights'][0]['addresses'][0]=0
            rejects(lambda:s.seal_resident(r));assert s.blocked and page.snapshot()['revoked']
        run('original_BO_'+kind+'_refused',bad_resident)
    def mutation_active(s,p,page,w,f,r,e):
        bind(s,page,f);s.seal_resident(r)
        rejects(lambda:s.interlock.before('driver reload',release_check=lambda:e.append('MUST_NOT_RELEASE')),'retains platform ownership')
        assert s.blocked and e==['revoke'] and page.snapshot()['revoked']
    run('active_native_mutation_revokes_before_release_and_is_refused',mutation_active)
    def release_failure(s,p,page,w,f,r,e):
        bind(s,page,f);s.seal_resident(r);page.revoke();w.stdin.close();w.wait(5);s.finish_native()
        def release():e.append('fresh_original_release_failed');raise RuntimeError('live refcount nonzero')
        rejects(lambda:s.interlock.before('remove',release_check=release),'live refcount nonzero')
        assert e==['revoke','fresh_original_release_failed'] and not s.interlock.retired
    run('fresh_release_failure_cannot_be_replaced_by_old_receipt',release_failure)
    def unknown_exit(s,p,page,w,f,r,e):
        bind(s,page,f);s.seal_resident(r);page.revoke();w.stdin.close();w.wait(5)
        s.page_observer=lambda:dict(revoked=True,active=False,unknown_io=True)
        rejects(s.finish_native,'retains ownership');assert not s.normal_terminal
    run('terminal_pidfd_does_not_clear_unknown_IO_policy',unknown_exit)
    def unexpected_exit(s,p,page,w,f,r,e):w.stdin.close();w.wait(5);rejects(s.observe,'owned native generation exited');assert s.blocked
    run('same_owned_pidfd_exit_revokes',unexpected_exit)
    # Exact wrapper invokes original command/service only after the new interlock.
    calls=[]
    class Original:
        def __init__(self):pass
        def command(self,argv,state_changing=False):calls.append(('command',state_changing));return 'original'
        def service(self,action):calls.append(('service',action));return 'original'
        def no_users(self,*,module_loaded):calls.append(('fresh_original_no_users',module_loaded))
    cls=interlocked_platform(types.SimpleNamespace(Platform=Original));platform=cls()
    platform.command(['list'],False);platform.command(['load'],True);platform.service('stop')
    assert platform.generation_interlock.serial==2 and calls==[('command',False),('command',True),('service','stop')]
    results.append(dict(test='original_PL_command_and_GDM_paths_both_interlocked',status='PASS_PC_WRAPPER'))
    platform._generation_release_check();assert calls[-1]==('fresh_original_no_users',Path('/sys/module/zocl').exists())
    results.append(dict(test='restore_reuses_original_loaded_or_absent_module_release_gate',status='PASS_PC_WRAPPER'))
    for inherit in (True,False):
        with tempfile.TemporaryDirectory(prefix='a12-live-borrow-') as root:
            p=FixturePorts(Path(root)/'source',time.monotonic_ns()+10_000_000_000)
            paths=[path for path,fd in p.base.locks];fds=[fd for path,fd in p.base.locks]
            worker=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],stdin=subprocess.PIPE,
                pass_fds=tuple(fds) if inherit else (),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                if inherit:inherited_lock_proof(paths,fds,worker.pid,os.getpid())
                else:rejects(lambda:inherited_lock_proof(paths,fds,worker.pid,os.getpid()))
            finally:worker.stdin.close();worker.wait(5);p.test_cleanup()
            results.append(dict(test='native_both_actual_flocks_inherited' if inherit else 'native_missing_inherited_locks_refused',status='PASS_PC_OS_HANDLES'))
    with tempfile.TemporaryDirectory(prefix='a12-live-lease-view-') as root:
        p=FixturePorts(Path(root)/'source',time.monotonic_ns()+10_000_000_000);calls=[]
        class OriginalOwner:
            @staticmethod
            def owner_check(owner):
                calls.append('fresh_full_SHA');assert sha(p.base.readers[0].path)==p.lease_sha256
        view=BoardPorts.__new__(BoardPorts);view.reader=p.base.readers[0];view.owner=types.SimpleNamespace(finished=False)
        view.platform=types.SimpleNamespace(owner=view.owner);view.original=types.SimpleNamespace(Owner=OriginalOwner)
        try:
            view.owner_check();assert calls==['fresh_full_SHA']
            view.reader.path.write_bytes(view.reader.path.read_bytes()+b' ');rejects(view.owner_check,'lease inode/metadata changed')
            assert calls==['fresh_full_SHA'] # stale inode/bytes cannot reuse an earlier verdict
        finally:p.test_cleanup()
        results.append(dict(test='anchored_original_lease_full_SHA_once_no_cached_verdict',status='PASS_PC_POLICY_ONLY'))
    rejects(load_original,'root ARM64');rejects(lambda:BoardPorts(None,None),'root ARM64')
    results.append(dict(test='Board_factory_cannot_be_overridden_on_PC',status='PASS_REFUSAL'))
    save(OUT/('SOURCE_TEST-'+a.tag+'.json'),dict(status='PASS_PC_LIVE_SOURCE_AND_ORIGINAL_BO_POLICY',tests=results,count=len(results),
        verification_layer='PC_OS_HANDLES_PLUS_EXPLICIT_SYNTHETIC_BOARD_POLICY_FIXTURES',actual_Board_health=False,actual_Board_BO_allocations=None,BOARD='NOT_TESTED'))
    print('PASS_PC_LIVE_SOURCE_AND_ORIGINAL_BO_POLICY',len(results))
if __name__=='__main__':main()
