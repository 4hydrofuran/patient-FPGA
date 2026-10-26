"""Reproduce the original release gate counting our O_PATH observer, then fix.

The PC proc proxy exposes this real process's stat/maps/fd table to the unaltered
collector. A private regular file is an explicit test-only accelerator alias.
No physical device, real module refcount or Board health is claimed.
"""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import zipfile
from livegen_evidence import ROOT,OUT,read,save,sha
from livegen_platform import import_original_verified
from livegen_source import Source,MutationInterlock
from livegen_fixtures import FixturePorts,context_fixture,resident_fixture
from plm_manager import ticks
from plm_page import Page
from request_journal_verified import digest

def main():
    os.umask(0o077);package=read(OUT/'PACKAGE_REVIEW.json');archive=ROOT/package['archive']['path'];assert sha(archive)==package['archive']['sha256']
    with zipfile.ZipFile(archive) as z:old_text=z.read('source/livegen_source.py').decode()
    old=types.ModuleType('known_old_source_v1');old.__file__=str(archive)+'!source/livegen_source.py';sys.modules[old.__name__]=old
    exec(compile(old_text,old.__file__,'exec'),old.__dict__)
    original=import_original_verified();release=importlib.import_module(original.__package__+'.accelerator_release_gate_v2')
    build=read(OUT/'BUILD-v2.json');records=[]
    for label,source_type,registry_type,exit_code in [('old',old.Source,old.MutationInterlock,0),('fixed',Source,MutationInterlock,0),('nonzero',Source,MutationInterlock,7)]:
        with tempfile.TemporaryDirectory(prefix='a12-opath-release-') as root:
            root=Path(root);ports=FixturePorts(root/'source',time.monotonic_ns()+30_000_000_000);page=Page(build['writer_library'],build['writer_sha256'])
            p=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read();sys.exit('+str(exit_code)+')'],stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);pidfd=os.pidfd_open(p.pid);source=source_type(ports,registry_type(),page.revoke)
            try:
                start=ticks(p.pid);source.attach_worker(p,pidfd,start,page.snapshot);facts=context_fixture(p.pid,start,ports.boot);ctx=digest(facts)
                cap=source.issue(facts);page.bind(p.pid,start,ctx);source.consume(cap,ctx);page.load_end();source.seal_resident(resident_fixture(facts))
                proxy=root/'proc';(proxy/'sys/kernel/random').mkdir(parents=True);(proxy/'sys/kernel/random/boot_id').write_text(ports.boot+'\n')
                myself=proxy/str(os.getpid());myself.mkdir()
                for name in ('stat','maps','fd'):(myself/name).symlink_to(Path('/proc')/str(os.getpid())/name,target_is_directory=name=='fd')
                before=release.collect(proxy,cards=(str(ports.attribute),));assert before['scan_complete'] and before['device_holders']
                page.revoke();p.stdin.close();p.wait(5)
                failure=None
                try:source.finish_native()
                except RuntimeError as e:failure=str(e)
                ports.base.observe();assert len(ports.base.locks)==2 # source never releases original lease/locks
                after=release.collect(proxy,cards=(str(ports.attribute),));assert after['scan_complete']
                refused=None
                try:release.require_release(after,0,True,boot_id=ports.boot)
                except RuntimeError as e:refused=str(e)
                if label=='old':assert source.normal_terminal and refused=='ACCELERATOR_DESCRIPTOR_STILL_OPEN' and not ports.nodes.closed
                elif label=='fixed':assert source.normal_terminal and refused is None and ports.nodes.closed and not after['device_holders']
                else:assert failure=='normal native exit not proven' and not source.normal_terminal
                records.append(dict(case=label,worker_exit_code=p.returncode,normal_terminal=source.normal_terminal,finish_refusal=failure,
                    observer_pins_closed=ports.nodes.closed,before=before,after=after,original_release_refusal=refused,
                    original_lease_dual_locks_retained=True,scope='PC_PROC_PROXY_REAL_OWN_FD_TABLE_EXPLICIT_REGULAR_FILE_ALIAS_SYNTHETIC_REFCOUNT0_NOT_BOARD'))
            finally:
                if p.stdin and not p.stdin.closed:p.stdin.close()
                p.wait(5)
                if source.pidfd is not None:os.close(source.pidfd);source.pidfd=None
                os.close(pidfd);ports.test_cleanup();page.close()
    save(OUT/'OPATH_RELEASE_COUNTEREXAMPLE.json',dict(status='PASS_ORIGINAL_RELEASE_GATE_WITHOUT_OBSERVER_EXEMPTION',
        rejected_old_review_archive_sha256=package['archive']['sha256'],old_source_sha256=__import__('hashlib').sha256(old_text.encode()).hexdigest(),
        records=records,BOARD='NOT_TESTED',real_module_refcount=None,old_archive_acceptance='NOT_ACCEPTED_FOR_RELEASE_INTERLOCK'))
    print('PASS_ORIGINAL_RELEASE_GATE_WITHOUT_OBSERVER_EXEMPTION')
if __name__=='__main__':main()
