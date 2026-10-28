import unittest
from recover_oops_once import COMMAND, BOOT


class RecoveryTests(unittest.TestCase):
    def test_one_normal_reboot_only(self):
        self.assertEqual(COMMAND.count('/usr/bin/systemctl reboot'), 1)
        for forbidden in ('--force', 'reboot -f', 'sysrq', 'rmmod', 'insmod',
                          'dfx-mgr-client', 'bootm', 'saveenv'):
            self.assertNotIn(forbidden, COMMAND)

    def test_exact_identity_original_and_no_compute_guards(self):
        for value in (BOOT, '6.8.12-a10irq1', 'sha256sum /etc/machine-id',
                      '/boot/firmware/image.fit', '/boot/firmware/boot.scr.uimg',
                      'test ! -e /home/ubuntu/a10-minimal-20261021-v1/compute.jsonl',
                      'test ! -e /home/ubuntu/a10-minimal-20261021-v1/approval.actual.json'):
            self.assertIn(value, COMMAND)
        self.assertTrue(COMMAND.startswith('set -e'))
        self.assertGreater(COMMAND.index('systemctl reboot'), COMMAND.index('sha256sum'))


if __name__ == '__main__':
    unittest.main()
