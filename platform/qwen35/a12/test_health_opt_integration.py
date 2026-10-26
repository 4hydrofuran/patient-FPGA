"""Run actual derived controller methods and frozen diagnostic gate on PC."""
import ast
import hashlib
from pathlib import Path
import queue
import sys
import threading
import time
import unittest
from health_opt import HealthSchedule,HealthBlocked

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evidence/model_pl_A/20261024-step10-v1/optimized/bundle-v1/control/support'))
from mlp_kernel_gate import MinimalGate

def methods():
    p=ROOT/'evidence/model_pl_A/20261024-health-opt-v1/controllers/health_opt_manager.py'
    tree=ast.parse(p.read_text(encoding='utf-8'))
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='receive']
    ns=dict(time=time,queue=queue,SPEC={'receive_seconds':2})
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(p),'exec'),ns)
    return ns

class IntegrationTests(unittest.TestCase):
    def test_actual_receive_reuses_fresh_observation(self):
        ns=methods();schedule=HealthSchedule();calls=[]
        class Owner:
            class platform:health_schedule=schedule
            def owner_check(self):calls.append('owner')
            def _health_observation(self):calls.append('health');return {}
        class Worker:
            messages=queue.Queue()
            def cancel(self,*a):raise AssertionError('no cancel expected')
        o=Owner();w=Worker();schedule.fresh(o._health_observation);w.messages.put({'type':'token'})
        self.assertEqual(ns['receive'](w,o,None),{'type':'token'})
        self.assertEqual(calls,['health'])
    def test_actual_receive_still_checks_when_idle(self):
        ns=methods();schedule=HealthSchedule();calls=[]
        class Owner:
            class platform:health_schedule=schedule
            def owner_check(self):calls.append('owner')
            def _health_observation(self):calls.append('health');return {}
        class Worker:messages=queue.Queue()
        w=Worker();w.messages.put({'type':'result'})
        ns['receive'](w,Owner(),None);self.assertEqual(calls,['owner','health'])
    def test_same_frozen_gate_rejects_new_warning(self):
        baseline=(ROOT/'evidence/model_pl_A/20261024-step10-v1/optimized/readback-v1/run-v1/baseline.raw.txt').read_text(encoding='utf-8')
        g=MinimalGate();boot='pc-test'
        self.assertTrue(g.observe(boot,baseline,hashlib.sha256(baseline.encode()).hexdigest())['allowed'])
        benign=baseline+'<6>[99999.000000] ordinary information\n'
        self.assertTrue(g.observe_action(boot,benign,None,'none')['allowed'])
        bad=benign+'<4>[99999.000001] new unreviewed warning\n'
        self.assertFalse(g.observe_action(boot,bad,None,'none')['allowed'])
        self.assertFalse(g.observe_action(boot,bad,None,'none')['allowed'])
    def test_frozen_gate_does_not_allow_action_warning_during_compute(self):
        baseline='<6>[    0.000000] baseline\n';g=MinimalGate();g.observe('b',baseline)
        raw=baseline+'<4>[    1.000000] zocl: loading out-of-tree module taints kernel.\n'
        self.assertFalse(g.observe_action('b',raw,None,'none')['allowed'])

if __name__=='__main__':unittest.main(verbosity=2)
