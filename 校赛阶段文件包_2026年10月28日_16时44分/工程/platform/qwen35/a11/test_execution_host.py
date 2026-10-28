"""Offline tests for exact-boot authorization and readback helper boundaries."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import launch_mlp_once as launch
from extract_uart_object import extract

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-integration-v1'


class ExecutionHost(unittest.TestCase):
    def test_exact_reviewed_baseline(self):
        raw=(EV/'candidate_readonly_01/baseline.raw.txt').read_bytes()
        self.assertEqual(launch.verify_fresh_log(SimpleNamespace(returncode=0,stderr=b'',stdout=raw)),raw)
        for p in (SimpleNamespace(returncode=1,stderr=b'',stdout=raw),
                  SimpleNamespace(returncode=0,stderr=b'error',stdout=raw),
                  SimpleNamespace(returncode=0,stderr=b'',stdout=raw+b'<4>new warning\n')):
            with self.assertRaisesRegex(RuntimeError,'BASELINE_CHANGED'):launch.verify_fresh_log(p)
    def test_wrong_boot_cannot_reserve_review(self):
        with patch.object(sys,'argv',['launch','11111111-1111-1111-1111-111111111111']):
            with self.assertRaisesRegex(RuntimeError,'EXACT_AUTHORIZED_BOOT'):launch.main()
    def test_missing_authorization(self):
        with patch.object(sys,'argv',['launch']):
            with self.assertRaisesRegex(RuntimeError,'EXACT_AUTHORIZED_BOOT'):launch.main()
    def test_generated_helpers_compile_without_execution(self):
        folder=EV/'execution-host-v1'
        for p in folder.glob('*.py'):ast.parse(p.read_text(),str(p))
        uart=(folder/'execute_once.ps1').read_text()
        self.assertIn("RETAINED\"') 360",uart)
        self.assertIn('Helper exceeds safe UART line budget',uart)
        self.assertNotIn("[ValidateSet('network'",uart)
        receipt=json.loads((EV/'execution_plan_01.json').read_text())
        self.assertEqual(receipt['exit_code'],0)
        plan=json.loads(receipt['stdout']);self.assertFalse(plan['board_contact']);self.assertTrue(plan['compute'])
    def test_probe_never_invokes_backend(self):
        tree=ast.parse((ROOT/'platform/qwen35/a11/native_probe.py').read_text())
        calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and isinstance(n.func.value,ast.Name) and n.func.value.id=='api']
        self.assertEqual(calls,['quantize'])
    def test_uart_extraction_requires_success(self):
        obj=dict(closed=True,exit_code=0,error=None,events=[dict(kind='result',text='echo\n{"status":"OK"}\nTAG:0\n')])
        self.assertEqual(extract(obj),dict(status='OK'))
        obj['exit_code']=2
        with self.assertRaises(ValueError):extract(obj)


if __name__=='__main__':unittest.main(verbosity=2)
