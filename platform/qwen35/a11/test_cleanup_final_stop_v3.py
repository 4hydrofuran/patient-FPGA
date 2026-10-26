"""Freeze the real final scan failure; prove hard-stop is not silently resumed."""
import json
from pathlib import Path
import unittest
from cleanup_controller_v3 import Controller,STEPS,observe_release

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-cleanup-board-v3'


class StopRegression(unittest.TestCase):
    def setUp(self):
        rows=[json.loads(x) for x in (EV/'final_readback_01/v3/lifecycle.jsonl').read_bytes().splitlines()]
        self.bad=[r['scan'] for r in rows if r['event']=='RELEASE_OBSERVATION'][-1]
        self.good=json.loads((EV/'final_readback_01/state.json').read_bytes())['scan']

    def test_real_failure_is_not_accepted_or_auto_retried(self):
        samples=[]
        def sample():samples.append(True);return self.bad,None,False
        with self.assertRaisesRegex(RuntimeError,'NON_TRANSIENT_SCAN_ERROR'):
            observe_release(sample,lambda *a:None,lambda *a:None,self.bad['boot_id'])
        self.assertEqual(len(samples),1)

    def test_complete_new_snapshot_does_not_reopen_hard_stop(self):
        import sys
        sys.path.insert(0,str(ROOT/'platform/local/a11-mlp-20261023-v1'))
        from accelerator_release_gate_v2 import require_no_users
        require_no_users(self.good,True,boot_id=self.good['boot_id'])
        class Fake:
            def __init__(self):self.applied=[]
            def emit(self,*a,**k):pass
            def gate(self,step):raise RuntimeError('NON_TRANSIENT_SCAN_ERROR')
            def apply(self,step):self.applied.append(step)
        io=Fake();c=Controller(io);c.index=STEPS.index('finalize')
        c.resume('test-final-first',0)
        self.assertEqual(c.state,'HARD_STOP_RECONCILE_ONLY');self.assertIsNone(c.inflight)
        with self.assertRaisesRegex(RuntimeError,'NOT_RESUMABLE'):
            c.resume('test-final-second',1)
        self.assertEqual(io.applied,[])
        self.assertEqual(c.status()['completed_steps'],list(STEPS[:-1]))


if __name__=='__main__':unittest.main(verbosity=2)
