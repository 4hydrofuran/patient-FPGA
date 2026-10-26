"""PC-only monitored boundary faults; inherited A10 release gate remains intact."""
import argparse
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
ap=argparse.ArgumentParser();ap.add_argument('--derived',type=Path,required=True)
args,remaining=ap.parse_known_args();sys.path.insert(0,str(args.derived))
from mlp_boundary_v2 import MlpBoundary
from test_boundary import Boundary,Parked


class Monitored(Boundary):
    def setUp(self):
        super().setUp();self.b.__class__=MlpBoundary;self.b.pulse=Mock()
    def test_normal_exit_does_not_itself_authorize_unload(self):
        import json
        self.path.write_text(json.dumps(self.result()));self.b.wait_normal(30)
        self.assertEqual(self.b.state,'EXITED_NORMAL');self.b.pulse.assert_called_once()
        self.assertEqual(MlpBoundary.check_release.__module__,'xrt_worker_boundary')
    def test_timeout_retains_no_kill(self):
        import subprocess
        self.b.process.wait.side_effect=subprocess.TimeoutExpired('PC_DOUBLE',.1)
        with patch('mlp_boundary_v2.time.monotonic',side_effect=[0.,0.,2.]):
            with self.assertRaises(Parked):self.b.wait_normal(1)
        self.b.process.kill.assert_not_called();self.b.process.terminate.assert_not_called()
        self.assertEqual(self.b.state,'QUARANTINED')
    def test_external_health_fault_does_not_wait_or_kill(self):
        self.b.pulse.side_effect=RuntimeError('thermal or kernel gate')
        with self.assertRaises(Parked):self.b.wait_normal(30)
        self.b.process.wait.assert_not_called();self.b.process.kill.assert_not_called()


if __name__=='__main__':unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
