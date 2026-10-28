"""No-device PC protocol, real journal syscalls and crash transcript fixtures."""
import argparse
import copy
import errno
import io
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from request_journal_verified import (BUNDLE, ROOT, FrozenProbe, VerifiedJournalMixin,
    VerifiedRequestController, RequestJournalBlocked, canonical)
from request_journal_audit import audit
import request_journal_audit as audit_module
from request_journal_candidate import RequestJournalCandidate
from resource_probe_policy import ProbeBlocked
from test_resource_probe import inventory

sys.path.insert(0,str(BUNDLE/'platform/qwen35/a12'))
import cpu01b_observer as ob
ob.ENABLED=False
from cpu01b_supervisor import OwnedWorker

EVIDENCE=None


class Worker(VerifiedJournalMixin,OwnedWorker):pass
class OldWorker(RequestJournalCandidate,OwnedWorker):pass


CHILD=r'''
import copy,json,os,signal,socket,sys
signal.signal(signal.SIGUSR1,lambda *_:None)
data=json.load(open(sys.argv[1]));s=socket.socket(fileno=int(os.environ['SP_A12_CONTROL_FD']));f=s.makefile('r')
seq={'router':0,'backend':0};job=0
def permit(phase,j):
    lane='router' if phase.startswith('router_') else 'backend';seq[lane]+=1
    req=dict(pid=os.getpid(),sequence=seq[lane],phase=phase,job=j)
    s.sendall((json.dumps(req)+'\n').encode());line=f.readline()
    return bool(line) and json.loads(line).get('allow') is True
if not permit('router_open',0) or not permit('device_open',0):sys.exit(8)
for i in range(1,73):
    if not permit('weight_load',i):sys.exit(9)
print(json.dumps(data['ready']),flush=True)
for line in sys.stdin:
    request=json.loads(line)
    if request['op']=='shutdown':permit('router_close',0);break
    row=copy.deepcopy(data['results'][request['id']]);n=data['counts'][request['id']];allowed=0
    for _ in range(n):
        job+=1
        if not permit('submit',job):break
        allowed+=1
    if allowed!=n:row=dict(type='fixture_refusal',allowed_fixture_permits=allowed,PL_calls=0)
    else:row['bridge']['a12_route']['host_verified_completions']=job
    print(json.dumps(row),flush=True)
f.close();s.close()
'''


def fixture_data():
    source=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02'
    results={};counts={}
    for name in ('app_R0','warm_prefix','app_hit'):
        r=json.loads((source/name/'result.json').read_text())
        r['fixture_domain']='PC_CONTROL_FIXTURE'
        r['prefix_cache']['binding_sha256']='b'*64
        r['bridge']['a12_route']=inventory()
        new=70 if name=='warm_prefix' else 37 if name=='app_hit' else 107
        decode=0 if name=='warm_prefix' else r['decode_calls']
        results[name]=r;counts[name]=72*((new+7)//8+decode)
    return dict(ready=dict(type='ready',execution_kind='FPGA_REAL',physical_ubatch=8,
        fixture_domain='PC_CONTROL_FIXTURE',prefix_cache=dict(enabled=True,binding_sha256='b'*64),
        bridge={'a12_route':inventory()}),results=results,counts=counts,
        domain='PC_CONTROL_FIXTURE_REPLAYS_PRIOR_CPU_TEXT_NO_MODEL_NO_PL')


class VerifiedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a12-journal-v2-')
        self.root=Path(self.temp.name);self.workers=[];self.checks={'owner':0,'health':0};self.thread_errors=[]
        self.hook=mock.patch.object(threading,'excepthook',side_effect=lambda args:self.thread_errors.append(str(args.exc_value)))
        self.hook.start()

    def tearDown(self):
        for worker in self.workers:
            if not worker.process.stdin.closed:worker.process.stdin.close()
            if worker.process.poll() is None:
                # CPU fixture descriptor cleanup only; never a board recovery path.
                try:worker.manager_sock.shutdown(socket.SHUT_WR)
                except OSError:pass
                worker.process.wait(timeout=5)
            worker.permission_thread.join(2);worker.reader_thread.join(2)
            for handle in (worker.stderr,worker.process.stdout,worker.manager_sock):handle.close()
            if hasattr(worker,'_journal'):worker._journal.close()
        self.hook.stop();self.temp.cleanup()

    def owner(self):self.checks['owner']+=1
    def health(self):self.checks['health']+=1;return dict(MemAvailable=1114112,CmaFree=98304)

    def launch(self,cls=Worker):
        data=fixture_data();path=self.root/('fixture-'+str(len(self.workers))+'.json');path.write_bytes(canonical(data))
        worker=cls([sys.executable,'-B','-c',CHILD,str(path)],directory=self.root/('worker-'+str(len(self.workers))),
            env=os.environ,health=self.health,owner_check=self.owner,max_runs=5000,max_loads=72,
            expires=time.monotonic()+120,real=False)
        self.workers.append(worker);ready=worker.get(10)
        return worker,ready

    def gate(self):
        w,ready=self.launch();return w,VerifiedRequestController(w,ready)

    def terminal(self,w):
        r=w.get(15);self.assertEqual(r.get('status'),'OK');return r

    def finish_all(self,w,g):
        for name in ('app_R0','warm_prefix','app_hit'):
            g.begin(name);g.finish(self.terminal(w))
        self.assertTrue(w.close(timeout=5));return audit(w.directory)

    def test_three_verified_requests_normal_close_and_readonly_audit(self):
        w,g=self.gate();r=self.finish_all(w,g)
        self.assertEqual(r['status'],'COMPLETE_PC_TRANSCRIPT_REQUIRES_INDEPENDENT_RELEASE')
        self.assertFalse(r['release_allowed']);self.assertFalse(r['replay_allowed'])
        self.assertEqual(r['simulated_submit_permits'],sum(fixture_data()['counts'].values()))
        self.assertTrue(w._permission_done.is_set());self.assertFalse(self.thread_errors)
        before=(w.directory/'events.jsonl').read_bytes();self.assertTrue(w.close())
        self.assertEqual(before,(w.directory/'events.jsonl').read_bytes())
        if EVIDENCE is not None:
            shutil.copytree(w.directory,EVIDENCE/'complete-transcript')
            (EVIDENCE/'COMPLETE_AUDIT.json').write_bytes(canonical(r)+b'\n')
            (EVIDENCE/'FRESH_CHECKS.json').write_bytes(canonical(dict(domain='PC_CONTROL_FIXTURE',
                checks=self.checks,simulated_permits=w.runs,records=len(w.records),PL_calls=0))+b'\n')

    def test_scalar_completion_bypass_is_disabled(self):
        w,g=self.gate();g.begin('app_R0');self.terminal(w)
        with self.assertRaises(RequestJournalBlocked):
            w.end_request('app_R0',cumulative_completions=w.runs,pending=0,state_cleared=True,outcome='VALIDATED')
        self.assertTrue(w.quarantined);self.assertFalse(w.close())

    def test_scalar_begin_and_changed_send_are_disabled(self):
        w,g=self.gate()
        with self.assertRaises(RequestJournalBlocked):w.begin_request('app_R0',100)
        self.assertFalse(w.close())
        w,g=self.gate();wire=g.begin('app_R0');wire['max_tokens']+=1
        with self.assertRaises(RequestJournalBlocked):w.send(wire)
        self.assertFalse(w.close())

    def test_terminal_evidence_damage_refuses_commit(self):
        mutations={
            'id':lambda r:r.update(id='foreign'),
            'status':lambda r:r.update(status='ERROR'),
            'type':lambda r:r.update(type='error'),
            'domain':lambda r:r.update(fixture_domain='BOARD'),
            'state':lambda r:r.update(state_cleared_before_response=False),
            'position':lambda r:r.update(state_position_after_clear=0),
            'count':lambda r:r['bridge']['a12_route'].update(host_verified_completions=1),
            'bool_count':lambda r:r['bridge']['a12_route'].update(host_verified_completions=True),
            'backend':lambda r:r['bridge']['a12_route'].update(execution_kind='CPU_REFERENCE'),
            'build':lambda r:r['bridge']['a12_route'].update(kernel_build_id=0),
            'bo':lambda r:r['bridge']['a12_route']['a11_io_bo_addresses'].__setitem__(0,0),
            'bo_weight_handle_bool':lambda r:r['bridge']['a12_route']['a11_live_weights'][0].update(handle=True),
            'binding':lambda r:r['prefix_cache'].update(binding_sha256='c'*64),
            'hit':lambda r:r['prefix_cache_request'].update(hit=True),
            'tokens':lambda r:r['prefix_cache_request'].update(new_tokens=1),
            'eos':lambda r:r.update(eos=False),
            'bool_gpu':lambda r:r.update(gpu_layers=False),
            'output':lambda r:r.update(output_tokens=[-1]),
            'prompt_tokens':lambda r:r.update(prompt_tokens=1),
            'logits':lambda r:r.update(last_prompt_logits_sha256=None),
            'content':lambda r:r.update(text='我最近服药了。'),
        }
        for name,change in mutations.items():
            with self.subTest(name=name):
                w,g=self.gate();g.begin('app_R0');r=self.terminal(w);change(r)
                with self.assertRaises((RequestJournalBlocked,ProbeBlocked,AssertionError,KeyError)):g.finish(r)
                self.assertTrue(w.quarantined);self.assertFalse(w.close())
                self.assertFalse((w.directory/'COMMIT-app_R0.json').exists())
                self.assertNotIn(audit(w.directory)['status'],('COMPLETE_PC_TRANSCRIPT_REQUIRES_INDEPENDENT_RELEASE',))

    def test_warm_prefix_and_hit_comparison_cannot_bypass(self):
        for kind in ('warm','hit'):
            w,g=self.gate();g.begin('app_R0');g.finish(self.terminal(w));g.begin('warm_prefix');r=self.terminal(w)
            if kind=='warm':r['prefix_cache']['entries'][0]['tokens']=69
            else:
                g.finish(r);g.begin('app_hit');r=self.terminal(w);r['last_prompt_logits_sha256']='c'*64
            with self.assertRaises((RequestJournalBlocked,ProbeBlocked)):g.finish(r)
            self.assertFalse(w.close())

    def test_final_fresh_health_failure_refuses_commit(self):
        for callback in ('health','owner_check'):
            w,g=self.gate();g.begin('app_R0');r=self.terminal(w)
            def failed():raise RuntimeError('PC fresh result '+callback+' fault')
            setattr(w,callback,failed)
            with self.assertRaises(RuntimeError):g.finish(r)
            self.assertFalse(w.close());self.assertFalse((w.directory/'COMMIT-app_R0.json').exists())

    def test_actual_fsync_failure_at_begin_latches_no_retry(self):
        w,g=self.gate();target=w._journal.fd;real=os.fsync
        def fail(fd):
            if fd==target:raise OSError(errno.EIO,'PC injected real journal fsync failure')
            return real(fd)
        with mock.patch.object(os,'fsync',side_effect=fail):
            with self.assertRaises(OSError):g.begin('app_R0')
        self.assertTrue(w._journal.blocked);self.assertTrue(w._persistence_failed)
        self.assertEqual(w.runs,0);self.assertFalse(w.close())
        self.assertFalse(audit(w.directory)['release_allowed'])

    def test_actual_partial_write_at_end_keeps_unknown_transcript(self):
        w,g=self.gate();g.begin('app_R0');r=self.terminal(w);target=w._journal.fd;real=os.write;calls=[]
        def fail(fd,data):
            if fd==target:
                calls.append(1)
                if len(calls)==1:return real(fd,data[:17])
                raise OSError(errno.ENOSPC,'PC injected full disk after partial write')
            return real(fd,data)
        with mock.patch.object(os,'write',side_effect=fail):
            with self.assertRaises(OSError):g.finish(r)
        self.assertEqual(len(calls),2);self.assertTrue(w._journal.blocked);self.assertFalse(w.close())
        self.assertEqual(audit(w.directory)['status'],'REJECTED_OR_TORN_RETAIN_OWNER')
        if EVIDENCE is not None:
            shutil.copytree(w.directory,EVIDENCE/'partial-write-transcript')

    def test_continuous_persistence_failure_unblocks_waiting_peer(self):
        w,g=self.gate();barrier=threading.Event()
        target=w._journal.fd;real=os.fsync
        def fail(fd):
            if fd==target:raise OSError(errno.EIO,'PC continuous journal fsync failure')
            return real(fd)
        def unhealthy():
            barrier.wait(5)
            raise RuntimeError('PC health fault while peer waits')
        w.health=unhealthy;g.begin('app_R0')
        with mock.patch.object(os,'fsync',side_effect=fail):
            barrier.set()
            self.assertTrue(w._permission_done.wait(5))
        peer=w.messages.get(timeout=5)
        self.assertEqual(peer['type'],'fixture_refusal')
        self.assertLess(peer['allowed_fixture_permits'],fixture_data()['counts']['app_R0'])
        self.assertTrue(w._persistence_failed);self.assertTrue(w._half_closed)
        self.assertFalse(w.close());self.assertFalse(self.thread_errors)

    def test_v1_actual_fsync_fault_characterization_is_preserved(self):
        w,ready=self.launch(OldWorker);w.begin_request('app_R0',1512)
        wire={k:v for k,v in FrozenProbe().requests[0].items() if k not in ('tokens','application')}
        barrier=threading.Event();target=w._journal.fd;real=os.fsync
        def unhealthy():
            barrier.wait(5)
            raise RuntimeError('PC v1 fault characterization')
        def fail(fd):
            if fd==target:raise OSError(errno.EIO,'PC v1 continuous fsync failure')
            return real(fd)
        w.health=unhealthy;w.send(wire)
        with mock.patch.object(os,'fsync',side_effect=fail):
            barrier.set();w.permission_thread.join(5)
        self.assertFalse(w.permission_thread.is_alive())
        self.assertTrue(w._journal.blocked);self.assertTrue(w.quarantined)
        self.assertTrue(self.thread_errors);self.assertIsNone(w.process.poll())
        with self.assertRaises(queue.Empty):w.messages.get(timeout=.1)
        proof=dict(status='REPRODUCED_V1_HANDLER_EXITS_BEFORE_PEER_EOF',domain='PC_ONLY_FAULT_CHARACTERIZATION',
            journal_latched=True,permission_thread_exited=True,child_still_waiting=True,
            manual_half_close_below_is_PC_FIXTURE_CLEANUP_NOT_BOARD_RECOVERY=True,PL_calls=0,BOARD='NOT_TESTED')
        if EVIDENCE is not None:(EVIDENCE/'V1_FAULT_REPRODUCTION.json').write_bytes(canonical(proof)+b'\n')
        w.manager_sock.shutdown(socket.SHUT_WR)  # Only after preserving the observed PC defect.
        self.assertEqual(w.messages.get(timeout=5)['type'],'fixture_refusal')

    def test_invalid_ready_isolation_and_bo_alignment(self):
        for damage in ('domain','count','alignment'):
            w,ready=self.launch()
            if damage=='domain':ready['fixture_domain']='BOARD'
            if damage=='count':ready['bridge']['a12_route']['host_verified_completions']=True
            if damage=='alignment':
                for address in ready['bridge']['a12_route']['a11_live_weights']:
                    address['addresses']=[n+1 for n in address['addresses']]
            with self.assertRaises((RequestJournalBlocked,AssertionError)):VerifiedRequestController(w,ready)
            self.assertTrue(w.quarantined);self.assertEqual(w.runs,0);self.assertFalse(w.close())

    def test_process_abrupt_exit_after_replayed_begin_is_not_completion(self):
        w,g=self.gate();self.finish_all(w,g)
        lines=(w.directory/'events.jsonl').read_bytes().splitlines(keepends=True)
        begin=next(i for i,line in enumerate(lines) if b'REQUEST_BEGIN_PC_CANDIDATE' in line)
        source=self.root/'replayed-BEGIN-prefix.bin';source.write_bytes(b''.join(lines[:begin+1]))
        target=self.root/'abrupt-writer';target.mkdir(mode=0o700)
        code='import os,sys; raw=open(sys.argv[1],"rb").read(); fd=os.open(sys.argv[2],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); n=os.write(fd,raw); assert n==len(raw); os.fsync(fd); os._exit(23)'
        run=subprocess.run([sys.executable,'-B','-c',code,str(source),str(target/'events.jsonl')],capture_output=True,timeout=5)
        self.assertEqual(run.returncode,23)
        result=audit(target);self.assertEqual(result['status'],'INCOMPLETE_UNKNOWN_RETAIN_OWNER')
        self.assertFalse(result['release_allowed']);self.assertFalse(result['replay_allowed'])
        if EVIDENCE is not None:
            shutil.copytree(target,EVIDENCE/'abrupt-writer-transcript')
            (EVIDENCE/'ABRUPT_WRITER.json').write_bytes(canonical(dict(result,writer_exit_code=23,
                scope='PC_WRITER_OF_REPLAYED_BEGIN_PREFIX_NOT_MODEL_MANAGER_POWER_LOSS'))+b'\n')

    def test_receipt_failure_after_durable_end_does_not_commit(self):
        w,g=self.gate();g.begin('app_R0');r=self.terminal(w)
        with mock.patch.object(w,'_write_receipt',side_effect=OSError(errno.ENOSPC,'PC receipt failure')):
            with self.assertRaises(OSError):g.finish(r)
        self.assertTrue(w.quarantined);self.assertFalse(w.close())
        raw=(w.directory/'events.jsonl').read_text();self.assertIn('REQUEST_END_PC_CANDIDATE',raw)
        self.assertFalse((w.directory/'COMMIT-app_R0.json').exists())
        self.assertEqual(audit(w.directory)['status'],'INCOMPLETE_UNKNOWN_RETAIN_OWNER')

    def test_commit_receipt_fsync_failure_remains_isolated_even_if_bytes_exist(self):
        w,g=self.gate();g.begin('app_R0');r=self.terminal(w);real=os.fsync
        def fail(fd):
            if Path('/proc/self/fd',str(fd)).readlink().name=='COMMIT-app_R0.json':
                raise OSError(errno.EIO,'PC receipt fsync failure after complete write')
            return real(fd)
        with mock.patch.object(os,'fsync',side_effect=fail):
            with self.assertRaises(OSError):g.finish(r)
        self.assertTrue((w.directory/'COMMIT-app_R0.json').exists())
        self.assertFalse(w.close());self.assertFalse(audit(w.directory)['release_allowed'])
        self.assertFalse(audit(w.directory)['status'].startswith('COMPLETE_PC_'))

    def test_zero_exit_without_router_close_is_not_normal_close(self):
        w,g=self.gate()
        for name in ('app_R0','warm_prefix','app_hit'):
            g.begin(name);g.finish(self.terminal(w))
        w.process.stdin.close();w.process.wait(timeout=5)
        self.assertEqual(w.process.returncode,0);self.assertFalse(w.close())
        self.assertFalse((w.directory/'NORMAL_CLOSE.json').exists())
        self.assertEqual(audit(w.directory)['status'],'REJECTED_OR_TORN_RETAIN_OWNER')

    def test_close_receipt_fsync_failure_is_not_proven_by_complete_file_bytes(self):
        w,g=self.gate()
        for name in ('app_R0','warm_prefix','app_hit'):
            g.begin(name);g.finish(self.terminal(w))
        real=os.fsync
        def fail(fd):
            if Path('/proc/self/fd',str(fd)).readlink().name=='NORMAL_CLOSE.json':
                raise OSError(errno.EIO,'PC normal close fsync failure after full write')
            return real(fd)
        with mock.patch.object(os,'fsync',side_effect=fail):self.assertFalse(w.close())
        self.assertTrue(w.quarantined);self.assertTrue(w._request_failed)
        # A reader cannot infer a historical fsync return value from present bytes.
        # Even format-complete audit NEVER grants runtime success/release/replay.
        result=audit(w.directory)
        self.assertEqual(result['status'],'COMPLETE_PC_TRANSCRIPT_REQUIRES_INDEPENDENT_RELEASE')
        self.assertFalse(result['release_allowed']);self.assertFalse(result['replay_allowed'])
        if EVIDENCE is not None:(EVIDENCE/'FSYNC_PROOF_LIMIT.json').write_bytes(canonical(dict(
            runtime_close_result=False,fixture_bytes_format_complete=True,audit=result,
            lesson='CURRENT_BYTES_DO_NOT_PROVE_PRIOR_FSYNC_SUCCESS_OR_RELEASE'))+b'\n')

    def test_journal_truncation_and_receipt_symlink_refused(self):
        w,g=self.gate()
        with (w.directory/'events.jsonl').open('ab') as f:f.write(b'foreign\n')
        with self.assertRaises(OSError):g.begin('app_R0')
        self.assertFalse(w.close())
        w,g=self.gate();g.begin('app_R0');r=self.terminal(w)
        (w.directory/'COMMIT-app_R0.json').symlink_to(self.root/'outside')
        with self.assertRaises(OSError):g.finish(r)
        self.assertFalse(w.close());self.assertFalse((self.root/'outside').exists())

    def test_readonly_auditor_rejects_crash_and_corruption_shapes(self):
        w,g=self.gate();self.finish_all(w,g)
        original=(w.directory/'events.jsonl').read_bytes();lines=original.splitlines(keepends=True)
        for kind in ('begin_only','missing_commit','missing_close','torn','tamper','reorder','duplicate_field','oversize','symlink','release_true'):
            with self.subTest(kind=kind):
                target=self.root/('audit-'+kind);shutil.copytree(w.directory,target)
                log=target/'events.jsonl'
                if kind=='begin_only':
                    begin=next(i for i,line in enumerate(lines) if b'REQUEST_BEGIN_PC_CANDIDATE' in line)
                    log.write_bytes(b''.join(lines[:begin+1]))
                if kind=='missing_commit':(target/'COMMIT-app_hit.json').unlink()
                if kind=='missing_close':(target/'NORMAL_CLOSE.json').unlink()
                if kind=='torn':log.write_bytes(original[:-7])
                if kind=='tamper':log.write_bytes(original.replace(b'"permit_count":1440',b'"permit_count":1439',1))
                if kind=='reorder':log.write_bytes(lines[1]+lines[0]+b''.join(lines[2:]))
                if kind=='duplicate_field':log.write_bytes(b'{"event":"a","event":"b"}\n')
                if kind=='oversize':log.write_bytes(b'x'*(512*1024+1))
                if kind=='symlink':log.unlink();log.symlink_to(w.directory/'events.jsonl')
                if kind=='release_true':
                    p=target/'NORMAL_CLOSE.json';r=json.loads(p.read_text());r['release_allowed']=True;p.write_bytes(canonical(r))
                before={p.name:p.lstat().st_size for p in target.iterdir()}
                result=audit(target)
                self.assertFalse(result['status'].startswith('COMPLETE_PC_'),(kind,result))
                self.assertFalse(result['release_allowed']);self.assertFalse(result['replay_allowed'])
                self.assertEqual(before,{p.name:p.lstat().st_size for p in target.iterdir()})

    def test_real_or_arm_worker_has_no_spawn_path(self):
        for kwargs in ({'real':True},{'real':False}):
            import request_journal_candidate as old
            with mock.patch.object(old.platform,'machine',return_value='aarch64'):
                with mock.patch('subprocess.Popen') as spawn:
                    with self.assertRaises(RequestJournalBlocked):Worker(**kwargs)
                    spawn.assert_not_called()

    def test_audit_rechecks_previous_file_identity_before_success(self):
        w,g=self.gate();self.finish_all(w,g);original=audit_module.strict_json;changed=[]
        def concurrent_change(raw):
            result=original(raw)
            if isinstance(result,dict) and 'last_record_sha256' in result and not changed:
                with (w.directory/'events.jsonl').open('ab') as f:f.write(b'changed-after-read\n')
                changed.append(True)
            return result
        with mock.patch.object(audit_module,'strict_json',side_effect=concurrent_change):result=audit(w.directory)
        self.assertTrue(changed);self.assertEqual(result['status'],'REJECTED_OR_TORN_RETAIN_OWNER')
        self.assertFalse(result['release_allowed']);self.assertFalse(result['replay_allowed'])


def main():
    global EVIDENCE
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True,type=Path);args=p.parse_args()
    args.evidence.mkdir(parents=True,exist_ok=False);EVIDENCE=args.evidence
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (EVIDENCE/'unittest.txt').write_text(stream.getvalue())
    summary=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),domain='PC_SOCKET_AND_OS_IO_FAULT_FIXTURES',
        BOARD='NOT_TESTED',PL_calls=0,model_runs=0,production_enabled=False,power_loss_test='NOT_PERFORMED')
    (EVIDENCE/'RESULT.json').write_bytes(canonical(summary)+b'\n')
    print(stream.getvalue());print(json.dumps(summary));return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
