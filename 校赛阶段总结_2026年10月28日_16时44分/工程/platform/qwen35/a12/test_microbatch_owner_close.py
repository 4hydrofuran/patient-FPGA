"""Actual nested Owner class: retain its FD until observer and child stop."""
import ast
import io
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
from microbatch_evidence import ROOT,OUT,save


class OwnerTests(unittest.TestCase):
    def owner(self,*,stopped=True,code=0,partial=False):
        tree=ast.parse((ROOT/'platform/qwen35/a12/microbatch_run.py').read_bytes())
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        node=next(n for n in run.body if isinstance(n,ast.ClassDef) and n.name=='Owner')
        class Base:
            def __init__(self):self.closes=0
            def close(self):self.closes+=1
        worker=types.SimpleNamespace(monitor=types.SimpleNamespace(stop=mock.Mock(return_value=stopped)))
        if not partial:worker.process=types.SimpleNamespace(poll=mock.Mock(return_value=code))
        scope=dict(OriginalOwner=Base,pending=[worker],owners=[])
        exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_candidate_owner_close','exec'),scope)
        return scope['Owner'](),worker
    def test_terminal_and_stopped_closes_exactly_once(self):
        owner,w=self.owner();owner.close();owner.close();self.assertEqual(owner.closes,1)
        self.assertTrue(owner.closed_after_observer_stop)
    def test_live_child_retains_owner_even_if_observer_stopped(self):
        owner,w=self.owner(code=None);owner.close();self.assertEqual(owner.closes,0)
        w.process.poll.return_value=2;owner.close();self.assertEqual(owner.closes,1)
    def test_stalled_observer_retains_owner_after_child_exit(self):
        owner,w=self.owner(stopped=False,code=2);owner.close();self.assertEqual(owner.closes,0)
        w.monitor.stop.return_value=True;owner.close();self.assertEqual(owner.closes,1)
    def test_pre_spawn_partial_initialization_has_no_child_to_wait_for(self):
        owner,w=self.owner(partial=True);owner.close();self.assertEqual(owner.closes,1)


if __name__=='__main__':
    target=OUT/'owner-close-tests-01';target.mkdir(exist_ok=False);stream=io.StringIO()
    r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (target/'unittest.txt').write_text(stream.getvalue());save(target/'RESULT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',
        tests=r.testsRun,errors=len(r.errors),failures=len(r.failures),PL_calls=0,BOARD='NOT_TESTED'))
    print(stream.getvalue());raise SystemExit(0 if r.wasSuccessful() else 1)
