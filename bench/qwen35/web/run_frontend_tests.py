"""Run A regressions and B's new dispatch check against the merged package."""
import argparse
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parent',type=Path,required=True);a=p.parse_args()
    window=a.parent.resolve()/'continuous';sys.path[:0]=[str(window/'web_gateway/src'),str(window),str(ROOT)]
    import patient_web
    assert Path(patient_web.__file__).resolve().is_relative_to(window/'web_gateway/src')
    suite=unittest.defaultTestLoader.discover(str(ROOT/'bench/qwen35/web'),pattern='test_*.py')
    spec=importlib.util.spec_from_file_location('b_latest_dispatch',window/'web_gateway/tests/gateway/test_backend_switch.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    suite.addTest(unittest.FunctionTestCase(m.test_switch_between_completed_turns_keeps_actual_delivery_provenance))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
