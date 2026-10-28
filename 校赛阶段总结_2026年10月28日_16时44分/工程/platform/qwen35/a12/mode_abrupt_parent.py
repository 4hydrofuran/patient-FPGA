"""Disposable PC coordinator: exit without closing its active session."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from mode_evidence import WORK
from mode_coordinator import ModeCoordinator

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--capsule',type=Path,required=True);a=p.parse_args()
    c=ModeCoordinator(WORK/('state-'+a.tag),a.capsule,trusted_worker=True);c.switch('PC_BATCH_CANDIDATE')
    c.launch('abrupt-parent-new-1');until=time.monotonic()+120
    while time.monotonic()<until:
        c.observe();r=c.active
        if r and r['page'] and r['page'].snapshot()['shared_claims']>=5:break
        time.sleep(.005)
    assert c.active and c.active['native'] and c.active['page'].snapshot()['shared_claims']>=5
    r=c.active
    print(json.dumps(dict(event='ABRUPT_COORDINATOR_READY',state_directory=str(c.journal.path),
        window_id=r['window_id'],tag=r['tag'],manager_pid=r['manager'].pid,manager_ticks=r['manager'].ticks,
        native_pid=r['native'].pid,native_ticks=r['native'].ticks)),flush=True)
    # Outer test acquires live pidfds before acknowledging this deliberate exit.
    assert sys.stdin.readline().strip()=='ACK_LIVE_HANDLES'
    os._exit(0)
