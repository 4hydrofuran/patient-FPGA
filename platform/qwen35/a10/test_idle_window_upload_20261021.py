from pathlib import Path
import unittest
from unittest.mock import patch

import upload_idle_window_20261021 as upload

V3_SHA = '1ccf6f2a437ea0932fd5de5b17c34696dcbd2d5cf95fd26fdce92b9e1efcd427'


class UploadPlanTests(unittest.TestCase):
    def test_original_v2_exact_paths_remain_valid(self):
        with patch.object(upload.subprocess, 'run', side_effect=AssertionError('board access')):
            commands, hashes = upload.commands()
        self.assertEqual(len(commands), 4)
        self.assertIn('mkdir ' + upload.REMOTE, commands[0][-1])
        self.assertIn(upload.REMOTE + '/bundle.pending.json', hashes)

    def test_fixed_v3_upload_and_readback_use_same_paths(self):
        bundle = upload.BUNDLE.parent / 'a10-candidate-idle-20261021-v3'
        remote = '/home/ubuntu/' + bundle.name
        commands, hashes = upload.commands(bundle, V3_SHA, remote, reuse_review=True)
        self.assertEqual(len(commands), 3)
        self.assertIn('mkdir ' + remote, commands[0][-1])
        self.assertEqual(commands[1][-1], 'ubuntu@192.168.2.2:' + remote + '/')
        self.assertIn(remote + '/bundle.pending.json', hashes)
        self.assertNotIn('candidate_idle_trial.py --execute', commands[-1][-1])
        self.assertIn('test -d ' + upload.REMOTE_REVIEW, commands[0][-1])

    def test_wrong_remote_and_other_paths_fail_before_verification(self):
        with patch.object(upload, 'verify_bundle', side_effect=AssertionError('unexpected read')):
            for path, remote in [(Path('/tmp/other'), '/home/ubuntu/other'),
                                 (upload.BUNDLE, '/boot/firmware/other')]:
                with self.assertRaises(RuntimeError):
                    upload.commands(path, upload.MANIFEST_SHA, remote)

    def test_manifest_change_rejected(self):
        with self.assertRaises(RuntimeError):
            upload.commands(manifest_sha='0' * 64)


if __name__ == '__main__':
    unittest.main(verbosity=2)
