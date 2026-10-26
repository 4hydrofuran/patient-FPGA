import io
import unittest
from unittest.mock import patch

import upload_isolated_idle as upload


class UploadTests(unittest.TestCase):
    def test_real_bundle_plan_only_additive_pinned_user_directory(self):
        commands, hashes = upload.plan('549452c7-1381-4d31-b959-b40c66a93343')
        self.assertEqual(len(commands), 3)
        self.assertEqual(len(hashes), 16)
        self.assertEqual(hashes['manifest.json'], upload.MANIFEST_SHA)
        self.assertIn('mkdir ' + upload.REMOTE, commands[0][-1])
        self.assertIn('StrictHostKeyChecking=yes', commands[0])
        self.assertIn('BindAddress=192.168.2.1', commands[0])
        all_commands = ' '.join(' '.join(c) for c in commands)
        for forbidden in ('insmod', 'rmmod', 'reboot', 'reset', 'sudo', 'dd ', 'saveenv', 'sh -c'):
            self.assertNotIn(forbidden, all_commands)

    def test_default_does_not_launch_connection(self):
        with patch.object(upload.subprocess, 'run', side_effect=AssertionError('connection forbidden')), \
                patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(upload.main(['--boot-id', '549452c7-1381-4d31-b959-b40c66a93343']), 0)

    def test_injected_boot_string_refused(self):
        with self.assertRaises(ValueError):
            upload.plan('boot; something')


if __name__ == '__main__':
    unittest.main()
