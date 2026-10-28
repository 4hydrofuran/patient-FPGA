import importlib.util
import json
from pathlib import Path
import queue
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/web'))
PINNED=ROOT/'evidence/model_pl_A/20261026-pl-authfix-board-v2/bundle-fixed-v2'
for path in (PINNED/'platform/qwen35/a12',PINNED/'control/support'):
    sys.path.insert(0,str(path))
from graphical_runtime import graphical_gate,settle_terminal
from interactive_case import CachedTransport


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=PINNED/'platform/qwen35/a12/cpu01b_kernel_gate.py'
        spec=importlib.util.spec_from_file_location('tested_kernel_gate',p)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cls.original=module.MinimalGate;cls.graphical=graphical_gate(module.MinimalGate)

    def test_actual_captured_browser_log_is_recorded_without_blocking_compute(self):
        evidence=json.loads((ROOT/'evidence/frontend_board_A/20261026-manual-session-v1/HEALTH_FAILURE.json').read_text())
        new=evidence['rejections'][0]['new_text'];baseline='<6>[ 0.000001] startup\n'
        old=self.original();new_gate=self.graphical()
        for gate in (old,new_gate):self.assertTrue(gate.observe_action('boot',baseline,None,'none')['allowed'])
        self.assertFalse(old.observe_action('boot',baseline+new,None,'none')['allowed'])
        result=new_gate.observe_action('boot',baseline+new,None,'none')
        self.assertTrue(result['allowed']);self.assertEqual(new_gate.previous,baseline+new)
        self.assertEqual(len(result['reviewed_advisories']),1)
        self.assertEqual(result['reviewed_advisories'][0]['review'],'AUDIT_RATE_LIMIT_NOTICE_NOT_ACCELERATOR_DIAGNOSTIC')
        failure=new_gate.observe_action('boot',baseline+new+'<3>[ 9000.0] zocl DMA timeout\n',None,'none')
        self.assertFalse(failure['allowed'])

    def test_continuity_and_boot_changes_remain_rejected(self):
        for boot,text in (('other','<6>[ 0.1] normal\n'),('boot','<6>[ 0.2] missing earlier log\n')):
            gate=self.graphical();gate.observe_action('boot','<6>[ 0.1] normal\n',None,'none')
            self.assertFalse(gate.observe_action(boot,text,None,'none')['allowed'])

    def test_receive_exception_is_not_replaced_by_late_terminal_or_infinite_wait(self):
        messages=queue.Queue();messages.put(dict(type='result',id='a12-1',status='ERROR'))
        saved=[]
        def fail(*a,**kw):raise RuntimeError('health rejected')
        worker=types.SimpleNamespace(messages=messages,send=lambda request:None)
        api=types.SimpleNamespace(receive=fail,save=lambda *a:saved.append(a))
        transport=CachedTransport(worker,object(),Path('/unused'),api)
        transport.send(dict(id='a12-1'))
        with self.assertRaisesRegex(RuntimeError,'health rejected'):transport.get(1)
        self.assertTrue(transport.inflight)
        self.assertTrue(settle_terminal(transport,timeout=.1))
        self.assertFalse(transport.inflight)
        self.assertFalse(saved[0][1]['delivered'])
        transport.inflight=True
        self.assertFalse(settle_terminal(transport,timeout=.01))
        self.assertTrue(transport.inflight)

    def test_verification_and_one_manual_answer_fit_existing_submission_budget(self):
        sent=[];worker=types.SimpleNamespace(send=sent.append)
        transport=CachedTransport(worker,object(),Path('/unused'),object(),maximum_questions=2)
        for rid in ('a12-1','a12-2'):
            transport.send(dict(id=rid));transport.inflight=False
        with self.assertRaises(RuntimeError):transport.send(dict(id='a12-3'))
        self.assertEqual(len(sent),2)
        self.assertEqual(72*(9+2*(5+23)),4680)
        self.assertLessEqual(4680,5000)


if __name__=='__main__':unittest.main()
