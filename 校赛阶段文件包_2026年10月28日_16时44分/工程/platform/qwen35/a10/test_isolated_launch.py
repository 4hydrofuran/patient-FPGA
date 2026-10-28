import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import launch_isolated_idle_once as launch


class BootstrapTests(unittest.TestCase):
    def test_review_pin_is_exact_original_raw_not_new_observation(self):
        root = Path(__file__).resolve().parents[3]
        raw = (root / 'evidence/board_platform/A10_20261023_isolated_idle_v4/candidate_review_01/baseline.raw.txt').read_bytes()
        previous = (root / 'evidence/board_platform/A10_20261023_isolated_idle_v1/final_readback_01/kernel.raw.txt').read_bytes()
        self.assertEqual(raw, previous)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), launch.BASELINE_SHA)
        self.assertEqual(launch.verify_fresh_log(SimpleNamespace(returncode=0, stdout=raw, stderr=b'')), raw)
        for item in (SimpleNamespace(returncode=0, stdout=raw+b'new warning\n', stderr=b''),
                     SimpleNamespace(returncode=1, stdout=raw, stderr=b''),
                     SimpleNamespace(returncode=0, stdout=raw, stderr=b'error')):
            with self.assertRaisesRegex(RuntimeError, 'REVIEW_REQUIRED_NO_TRIAL'):
                launch.verify_fresh_log(item)

    def test_wrong_boot_never_opens_bundle_or_executes(self):
        with patch.object(launch.sys, 'argv', ['helper', 'old']), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('read forbidden')), \
                patch.object(launch.os, 'execv', side_effect=AssertionError('exec forbidden')):
            with self.assertRaisesRegex(RuntimeError, 'EXACT_AUTHORIZED_BOOT'):
                launch.main()

    def test_host_upload_stage_review_and_readback_use_same_new_bundle(self):
        import upload_isolated_idle as upload
        import stage_isolated_idle as stage
        import isolated_candidate_readonly as readonly
        self.assertEqual(upload.MANIFEST_SHA, launch.MANIFEST_SHA)
        self.assertEqual(stage.MANIFEST_SHA, launch.MANIFEST_SHA)
        self.assertEqual(readonly.MANIFEST_SHA, launch.MANIFEST_SHA)
        self.assertEqual(upload.BUNDLE.name, launch.ROOT.name)
        self.assertEqual(stage.TARGET, launch.ROOT)
        self.assertEqual(readonly.ROOT, launch.ROOT)
        text = (Path(__file__).parent / 'read_isolated_result.py').read_text()
        self.assertIn(str(launch.ROOT).replace('\\', '/'), text)
        self.assertIn(launch.MANIFEST_SHA, text)

    def test_consumed_v3_cleanup_pin_retained_and_not_replayed(self):
        root = Path(__file__).resolve().parents[3]
        raw = (root / 'evidence/board_platform/A10_20261023_isolated_idle_v1/final_readback_01/prepl-cleanup.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), launch.PRIOR_CLEANUP_SHA)
        self.assertNotEqual(launch.PRIOR, launch.ROOT)


if __name__ == '__main__':
    unittest.main()
