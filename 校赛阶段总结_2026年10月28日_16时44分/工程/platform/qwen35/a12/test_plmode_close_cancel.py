"""Cancellation after verified native-context close must not corrupt exit ACK."""
import os
from pathlib import Path
from plmode_evidence import OUT,read,save
from plmode_coordinator import Coordinator

def main():
    os.umask(0o077);build=OUT/'BUILD-v2.json';b=read(build);c=Coordinator(Path(b['workspace'])/'cancel-after-context-close',build,trusted_candidate=True)
    c.start('late-cancel');entry=c.active;m=entry['manager']
    for _ in range(3):c.request_next()
    m.PC_after_native_closed=lambda:c.cancel(log=False)
    refused=None
    try:c.finish_native()
    except RuntimeError as e:refused=str(e)
    assert refused=='cancelled result cannot complete mode window' and c.phase=='FAILED_DRAINED_PC'
    p=entry['page']();assert p['claims']==2880 and p['revoked'] and not p['unknown_io'] and not p['active']
    assert m.closed and m.process.returncode==0 and m.native_close_verified.is_set() and m.provider.binding.source.normal_terminal
    assert entry['proof']['worker_exit_code']==0 and not entry['proof']['release_allowed']
    c.close();save(OUT/'LATE_CLOSE_CANCEL_TEST.json',dict(status='PASS_CANCELLED_MODE_OUTCOME_RETAINS_VALID_NATIVE_CLOSE_ACK',
        window_outcome='WINDOW_FAILED_NOT_DELIVERED_BY_COORDINATOR',native_exit_code=0,claims=2880,unknown_io=False,original_page_not_reset=True,
        hardware_release_inferred=False,BOARD='NOT_TESTED'))
    print('PASS_CANCELLED_MODE_OUTCOME_RETAINS_VALID_NATIVE_CLOSE_ACK')
if __name__=='__main__':main()
