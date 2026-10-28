import unittest
from audit_full_zocl import check_info
from audit_boot_candidate import archive_name
from package_irq2 import config_difference, validate_build_receipt, WORK


class Irq2Tests(unittest.TestCase):
    def receipt(self):
        return dict(exit_code=0, argv=['wsl.exe', 'bash',
            '/mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/build_irq2.sh', 'resume1'],
            stdout='a' * 64 + '  ' + str(WORK / 'build/arch/arm64/boot/Image') +
            '\nPC_FULL_KERNEL_ONLY_NOT_BOARD_NOT_DEPLOYED\n')

    def test_completed_build_receipt_matches_image(self):
        validate_build_receipt(self.receipt(), 'a' * 64)

    def test_interrupted_build_receipt_rejected(self):
        r = self.receipt()
        r['exit_code'] = 15
        with self.assertRaises(RuntimeError):
            validate_build_receipt(r, 'a' * 64)

    def test_wrong_build_or_missing_completion_rejected(self):
        r = self.receipt()
        r['argv'][-1] = 'initial'
        with self.assertRaises(RuntimeError):
            validate_build_receipt(r, 'a' * 64)
        r = self.receipt()
        r['stdout'] = r['stdout'].splitlines()[0]
        with self.assertRaises(RuntimeError):
            validate_build_receipt(r, 'a' * 64)

    def test_stale_image_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_build_receipt(self.receipt(), 'b' * 64)

    def test_release_explicit_and_old_default_remains(self):
        raw = b'vermagic=6.8.12-a10irq2 SMP preempt mod_unload modversions aarch64\0version=2.18.0\0'
        self.assertIn('irq2', check_info(raw, '6.8.12-a10irq2'))
        with self.assertRaises(ValueError):
            check_info(raw)

    def test_archive_release_not_mixed(self):
        self.assertEqual(archive_name('lib/modules/6.8.12-a10irq2/kernel/test.ko',
                                      '6.8.12-a10irq2'), 'kernel/test.ko')
        with self.assertRaises(ValueError):
            archive_name('lib/modules/6.8.12-a10irq1/kernel/test.ko', '6.8.12-a10irq2')

    def test_config_only_identity_change(self):
        old = 'CONFIG_LOCALVERSION="-a10irq1"\nCONFIG_VERSION_SIGNATURE="old"\nCONFIG_X=y'
        new = 'CONFIG_LOCALVERSION="-a10irq2"\nCONFIG_VERSION_SIGNATURE="new"\nCONFIG_X=y'
        self.assertEqual(len(config_difference(old, new)), 4)
        with self.assertRaises(ValueError):
            config_difference(old, new.replace('CONFIG_X=y', 'CONFIG_X=n'))


if __name__ == '__main__':
    unittest.main()
