"""Use pinned real-PC runner with a derived health worker; no BOARD entry."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import types
from unittest import mock

from fresh_identity_io import FreshCheckedFile,FreshMaps
from health_fence_evidence import ROOT,OUT,PRIOR,read,save,sha,pin
from native_health_fence import HealthFencedNativeWorker
from request_journal_verified import require

PINNED_RUNNER='329f6476be73f155ae5e1159751512442bf81346815e626b046575f99259e5d0'


def run(mode,tag,*,fault=None,identity_mode='persistent'):
    path=ROOT/'platform/qwen35/a12/native_request_run.py'
    require(sha(path)==PINNED_RUNNER,'frozen runner changed')
    module=types.ModuleType('health_fence_pinned_runner');module.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    module.OUT=OUT
    old_owner=module.PCOwner
    workers=[];owners=[];injection=threading.Event();publication=[]

    class LocalOwner(old_owner):
        def __init__(self,path):
            super().__init__(path);owners.append(self)
            self.lease=path.with_name('pc-identity.json')
            self.raw=b'{"domain":"PC_PRIVATE_IDENTITY_FIXTURE","BOARD":false}\n'
            self.lease.write_bytes(self.raw);self.lease.chmod(0o600)
            self.expected=hashlib.sha256(self.raw).hexdigest()
            self.checked=FreshCheckedFile(self.lease,self.expected,expected_bytes=self.raw)
            self.maps=FreshMaps();self.identity_mode=identity_mode;self.extra_checks=0
        def check(self):
            super().check()
            if self.identity_mode=='persistent':self.checked.check();self.maps.check()
            else:
                # Same candidate predicates, but reopen/reallocate every time.
                with_reader=FreshCheckedFile(self.lease,self.expected,expected_bytes=self.raw)
                try:pass # constructor performs the same fresh full check
                finally:with_reader.close()
                with_maps=FreshMaps()
                try:with_maps.check()
                finally:with_maps.close()
            self.extra_checks+=1
        def health(self):
            if injection.is_set():
                publication.append(time.monotonic_ns())
                raise RuntimeError('PC injected monitor fault while durable journal append is blocked')
            return super().health()
        def close(self):
            self.checked.close();self.maps.close();super().close()

    class Worker(HealthFencedNativeWorker):
        def __init__(self,*args,**kw):
            self._injected=False;super().__init__(*args,**kw);workers.append(self)
        def _durable(self,**row):
            trigger=(fault=='permit_log' and row.get('event')=='PERMISSION' and
                row.get('request',{}).get('phase')=='submit' and row['request']['job']==1 or
                fault=='end_log' and row.get('event')=='REQUEST_END_PC_CANDIDATE')
            if trigger and not self._injected:
                self._injected=True;actual=self._journal.append
                def blocked_append(payload):
                    injection.set();started=time.monotonic_ns()
                    with self.monitor.cv:
                        require(self.monitor.cv.wait_for(lambda:self.monitor.fault is not None,2),
                            'monitor failed to publish independently of journal append')
                    # Finish the actual original append after the simulated stall.
                    # This leaves the durable allow/END candidate for forensics.
                    actual(payload)
                    save(OUT/('run-'+tag)/'INJECTION.json',dict(kind=fault,started_ns=started,
                        published_ns=publication[0],finished_ns=time.monotonic_ns(),
                        actual_original_append_completed=True,disk_lock_held_by_protocol=True,
                        old_budget_not_refunded=True,BOARD='NOT_TESTED'))
                with mock.patch.object(self._journal,'append',side_effect=blocked_append):
                    return super()._durable(**row)
            return super()._durable(**row)

    module.PCOwner=LocalOwner;module.NativeJournalWorker=Worker
    source=[pin(ROOT/'platform/qwen35/a12'/n) for n in
        ('fresh_identity_io.py','health_fence.py','native_health_fence.py','native_health_run.py')]
    try:module.run(mode,tag,PRIOR/'BUILD-v2.json')
    finally:
        target=OUT/('run-'+tag)
        if target.exists():
            save(target/'HEALTH_FENCE.json',dict(source_at_launch=source,identity_mode=identity_mode,
                monitor=[w.monitor.status() for w in workers],
                result_boundaries=[w.health_result_boundaries for w in workers],
                owners=[dict(fresh_identity_checks=o.extra_checks,persistent_file_opens=o.checked.opens,
                    persistent_file_bytes=o.checked.bytes_read,persistent_maps_bytes=o.maps.bytes_read,
                    PC_identity_fixture=True,board_dual_lock_lease='NOT_PROVEN') for o in owners],
                fault_injection=fault,actually_injected=injection.is_set(),board_contacted=False,
                no_snapshot_reuse=True,goal_status='active'))
        # The pinned runner waits for cooperative CPU exit and protocol threads.
        # Never close the owner's handles behind a live observation callback.
        for w in workers:w.monitor.stop()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['strict','request'],required=True)
    p.add_argument('--tag',required=True);p.add_argument('--fault',choices=['permit_log','end_log'])
    p.add_argument('--identity-mode',choices=['persistent','reopen'],default='persistent')
    a=p.parse_args();run(a.mode,a.tag,fault=a.fault,identity_mode=a.identity_mode)
