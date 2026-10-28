"""Real HealthFence threads + delayed durable-call proxy, no device/model run."""
import json
import os
import threading
import time
from types import SimpleNamespace
from plm_manager import Manager as Original
from health_fence import HealthFence
from promptpl_manager import legacy_scope
from promptpl_evidence import OUT,save

def exercise(method,fail_during_io=False):
    packets=[];rows=[];bad=threading.Event();faults=[];m=SimpleNamespace()
    m.p=SimpleNamespace(pid=os.getpid());m.fault=None;m.lock=threading.RLock();m.legacy_sequences={'backend':38,'router':1}
    m.router=True;m.device=True;m.bound=True;m.active=None;m.completed=[];m.loads=37
    m._owned=lambda:None;m._valid=lambda q,s:Original._valid(m,q,s);m._guard=lambda:not bad.is_set() and m.fault is None
    m.legacy=SimpleNamespace(sendall=packets.append)
    def observe():
        if bad.is_set():raise RuntimeError('synthetic health failure during lifecycle fsync')
        return dict(PC_fixture=True,checked_monotonic_ns=time.monotonic_ns())
    def on_fault(reason):m.fault=reason;faults.append(reason)
    m.monitor=HealthFence(observe,on_fault=on_fault,interval_s=.01)
    def append(event,**data):
        rows.append(dict(event=event,**data));time.sleep(.1)
        if fail_during_io:bad.set()
        time.sleep(.25) # measured durable-call blocking proxy, not disk fsync proof
    m.journal=SimpleNamespace(append=append);error=None
    try:method(m,dict(sequence=39,pid=os.getpid(),job=38,phase='weight_load'))
    except RuntimeError as exc:error=str(exc)
    finally:m.monitor.stop()
    status=m.monitor.status()
    return dict(error=error,sent=[json.loads(p) for p in packets],rows=len(rows),faults=faults,
        max_age_ns=status['max_age_ns'],health_fault_latched=m.fault is not None)

def main():
    before=exercise(Original._legacy_message);after=exercise(legacy_scope['_legacy_message']);revoked=exercise(legacy_scope['_legacy_message'],True)
    assert before['error']=='foreign/reused/stale health ticket' and not before['sent']
    assert after['error'] is None and after['sent']==[dict(sequence=39,allow=True)]
    assert revoked['error'] is not None and not revoked['sent'] and revoked['health_fault_latched']
    assert all(r['max_age_ns']==250000000 and r['rows']==1 for r in (before,after,revoked))
    save(OUT/'LIFECYCLE_FENCE_TEST.json',dict(status='PASS_FRESH_LIFECYCLE_AUTHORIZATION_AFTER_DURABLE_CALL_WITH_UNCHANGED_FAULT_LATCH_AND_250MS_BOUND',
        before=before,after=after,health_failure_during_io=revoked,scope='REAL_HEALTHFENCE_THREADS_WITH_EXPLICIT_BLOCKING_JOURNAL_AND_HEALTH_PROXIES',BOARD='NOT_TESTED'))
    print('PASS_LIFECYCLE_FENCE_AFTER_IO_UNCHANGED_250MS_AND_FAULT_LATCH')
if __name__=='__main__':main()
