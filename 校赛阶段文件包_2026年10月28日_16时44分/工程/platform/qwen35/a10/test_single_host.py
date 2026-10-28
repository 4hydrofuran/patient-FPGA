"""PC-only pinned package/host plans. Never execute a board command."""
import ast
import base64
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import unittest
from types import SimpleNamespace

import single_compute_policy as policy
import upload_isolated_single as upload
import stage_isolated_single as stage
import single_candidate_readonly as candidate
import launch_isolated_single_once as launch
import fetch_single_result as fetch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class HostTests(unittest.TestCase):
    def test_frozen_package_and_live_sources_match_without_authorization(self):
        manifest = policy.verify_bundle(upload.BUNDLE, upload.MANIFEST_SHA)
        self.assertEqual(len(manifest['files']), 20)
        self.assertFalse((upload.BUNDLE/'review.json').exists())
        for name in policy.SOURCES:
            self.assertEqual(policy.digest(HERE/name), manifest['files'][name]['sha256'])
        self.assertEqual(stage.MANIFEST_SHA, candidate.MANIFEST_SHA)
        self.assertEqual(stage.MANIFEST_SHA, launch.MANIFEST_SHA)
        self.assertEqual(stage.MANIFEST_SHA, upload.MANIFEST_SHA)

    def test_upload_fixed_additive_pinned_no_execute(self):
        commands, hashes = upload.plan(launch.BOOT)
        self.assertEqual(len(commands), 3)
        self.assertEqual(len(hashes), 21)
        text = json.dumps(commands)
        self.assertIn('StrictHostKeyChecking=yes', text)
        self.assertIn('192.168.2.1', text)
        self.assertIn('mkdir '+upload.REMOTE, text)
        self.assertNotIn('mkdir -p', text)
        self.assertFalse(any(word in text for word in ('insmod', 'rmmod', 'systemctl reboot', 'dfx-mgr-client -load')))
        with self.assertRaises(ValueError):
            upload.plan('not-a-boot')

    def test_baseline_exact_bytes_required_no_autoapproval(self):
        raw = (ROOT/'evidence/board_platform/A10_20261023_isolated_idle_v4/result_readback_01/kernel.raw.txt').read_bytes()
        self.assertEqual(launch.verify_fresh_log(SimpleNamespace(returncode=0, stderr=b'', stdout=raw)), raw)
        for proc in (SimpleNamespace(returncode=1, stderr=b'', stdout=raw),
                     SimpleNamespace(returncode=0, stderr=b'warn', stdout=raw),
                     SimpleNamespace(returncode=0, stderr=b'', stdout=raw+b'<3>[9999] new error\n')):
            with self.assertRaises(RuntimeError):
                launch.verify_fresh_log(proc)

    def test_stage_and_reader_remain_separate_from_execution(self):
        for name in ('stage_isolated_single.py', 'single_candidate_readonly.py', 'read_single_result.py'):
            source = (HERE/name).read_text()
            ast.parse(source)
            self.assertNotIn('ctypes', source)
            self.assertNotIn('execv(', source)
            self.assertIn('a10-isolated-single-20261023-v1', source)
        self.assertIn('len(manifest[\'files\']) == 20', (HERE/'stage_isolated_single.py').read_text())

    def test_readback_cannot_invoke_cleanup(self):
        argv, pin = fetch.plan()
        self.assertEqual(pin, policy.digest(HERE/'read_single_result.py'))
        self.assertIn('StrictHostKeyChecking=yes', argv)
        with self.assertRaises(RuntimeError):
            fetch.plan(cleanup=True)

    @unittest.skipUnless(os.name == 'nt', 'Windows host plan parser')
    def test_powershell_three_plans_and_tty_caps_without_board_contact(self):
        for step, helper in (('root_stage', 'stage_isolated_single.py'),
                             ('candidate_readonly', 'single_candidate_readonly.py'),
                             ('execute_single', 'launch_isolated_single_once.py')):
            proc = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE/'single_prepare_uart.ps1'),
                '-Step', step, '-ExpectedBoot', launch.BOOT, '-ValidateOnly'], capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            plan = json.loads(proc.stdout)
            self.assertFalse(plan['board_contact'])
            self.assertEqual(plan['compute'], step == 'execute_single')
            command = plan['command']
            self.assertLessEqual(len(command.encode())+128, 4094)
            blob = re.search(r"b64decode\('([^']+)'\)", command)[1]
            self.assertEqual(gzip.decompress(base64.b64decode(blob)), (HERE/helper).read_bytes())

    @unittest.skipUnless(os.name == 'nt', 'Windows host authorization parser')
    def test_missing_authorization_rejected_before_serial(self):
        proc = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
            '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE/'single_prepare_uart.ps1'),
            '-Step', 'execute_single', '-ExpectedBoot', launch.BOOT], capture_output=True, timeout=10)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b'Explicit authorized step', proc.stderr)


if __name__ == '__main__':
    unittest.main()
