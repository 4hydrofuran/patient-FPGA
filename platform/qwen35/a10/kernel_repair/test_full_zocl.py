import unittest
from audit_full_zocl import check_info, RELEASE


class CandidateInfoTests(unittest.TestCase):
    def info(self, release=RELEASE, version='2.18.0'):
        return ('vermagic=' + release + ' SMP preempt mod_unload modversions aarch64\0version=' + version + '\0').encode()

    def test_new_release(self):
        self.assertIn(RELEASE, check_info(self.info()))

    def test_old_release_rejected(self):
        with self.assertRaises(ValueError):
            check_info(self.info('6.8.0-1015-xilinx'))

    def test_version_and_missing_fields_rejected(self):
        for raw in (self.info(version='2.23.0'), b'', b'version=2.18.0\0'):
            with self.assertRaises(ValueError):
                check_info(raw)

    def test_duplicate_metadata_rejected(self):
        for raw in (self.info() * 2, self.info() + b'version=2.18.0\0'):
            with self.assertRaises(ValueError):
                check_info(raw)

    def test_other_arch_or_flags_rejected(self):
        for raw in (self.info().replace(b'aarch64', b'x86_64'), self.info().replace(b' preempt', b'')):
            with self.assertRaises(ValueError):
                check_info(raw)


if __name__ == '__main__':
    unittest.main()
