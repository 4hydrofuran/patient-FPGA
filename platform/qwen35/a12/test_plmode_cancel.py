"""No launch after a latched cancel; cancellation revokes before ledger lock."""
import os
from pathlib import Path
import threading
import time
from plmode_evidence import OUT,read,save
from plmode_coordinator import Coordinator

def main():
    os.umask(0o077);build=OUT/'BUILD-v2.json';b=read(build);root=Path(b['workspace']);results=[]
    c=Coordinator(root/'cancel-before-launch',build,trusted_candidate=True)
    try:c.start('cancel-before',fault='cancel_before_launch')
    except RuntimeError as e:assert 'mode cancelled before native launch' in str(e)
    else:raise AssertionError('latched cancellation launched a native')
    assert c.phase=='FAILED_NO_NATIVE_PC' and c.active['manager'].p is None and not c.active['manager'].launch_attempted
    assert c.active['page'] is None and c.active['proof']['native_not_launched'] and c.active['manager'].page.snapshot()['revoked']
    c.close();results.append(dict(test='cancel_latched_before_Popen',native_launched=False,status='PASS_PC_ONLY'))
    c=Coordinator(root/'cancel-under-held-ledger-lock',build,trusted_candidate=True);c.start('cancel-ready')
    entry=c.active;started=threading.Event();errors=[]
    def cancel():
        started.set()
        try:c.cancel()
        except BaseException as e:errors.append(str(e))
    with c.lock:
        thread=threading.Thread(target=cancel);thread.start();assert started.wait(1);until=time.monotonic()+2
        while not entry['page']()['revoked'] and time.monotonic()<until:time.sleep(.001)
        assert entry['page']()['revoked'] and thread.is_alive()
    thread.join(5);assert not thread.is_alive() and not errors
    proof=c.observe();assert proof['native_pidfd_terminal'] and proof['page']['revoked'] and c.phase=='FAILED_DRAINED_PC'
    assert entry['manager'].control_results==[] and entry['page']()['claims']==0
    c.close();results.append(dict(test='native_revoke_visible_before_coordinator_ledger_lock',status='PASS_PC_ONLY',claims=0))
    save(OUT/'CANCELLATION_TEST.json',dict(status='PASS_CANCEL_LATCH_AND_ATOMIC_ORDER',tests=results,BOARD='NOT_TESTED',physical_release_allowed=False))
    print('PASS_CANCEL_LATCH_AND_ATOMIC_ORDER')
if __name__=='__main__':main()
