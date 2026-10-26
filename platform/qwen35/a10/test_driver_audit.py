import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from audit_zocl_module import compare_versions, sections
from verify_driver_inputs import check_package, check_index


def versions():
    return struct.pack('<II8s', 16, 123, b'test') + b'\0'*9


class DriverAuditTests(unittest.TestCase):
    def test_crc_exact(self):
        self.assertEqual(len(compare_versions(versions(), '0x7b test vmlinux EXPORT_SYMBOL')), 1)

    def test_crc_mismatch_and_missing(self):
        for symvers in ('0x7c test vmlinux EXPORT_SYMBOL', '0x7b other vmlinux EXPORT_SYMBOL'):
            with self.assertRaises(ValueError): compare_versions(versions(), symvers)

    def test_malformed_next_and_terminator(self):
        for raw in (struct.pack('<II', 0xfffffff0, 123) + b'x'*20, versions()[:-1], versions()+b'X'):
            with self.assertRaises(ValueError): compare_versions(raw, '0x7b test vmlinux EXPORT_SYMBOL')

    def test_legacy_format_rejected(self):
        with self.assertRaises(ValueError): compare_versions(struct.pack('<Q56s', 123, b'test'), '0x7b test vmlinux EXPORT_SYMBOL')

    def test_short_versions(self):
        for raw in (b'', b'x'*63):
            with self.assertRaises(ValueError): compare_versions(raw, '')

    def test_not_arm_module(self):
        with self.assertRaises(ValueError): sections(b'not an ELF')

    def test_package_and_index_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'data'; file.write_bytes(b'abc')
            sha = hashlib.sha256(b'abc').hexdigest()
            stanza = f'Package: test\nVersion: 1\nArchitecture: arm64\nFilename: pool/test.deb\nSize: 3\nSHA256: {sha}\n'
            self.assertEqual(check_package(stanza, 'test', '1', file)['SHA256'], sha)
            release = Path(tmp)/'release'; release.write_text(f'\nSHA256:\n {sha} 3 test.gz\nSHA512:\n')
            check_index(release, file, 'test.gz')
            file.write_bytes(b'abd')
            with self.assertRaises(ValueError): check_package(stanza, 'test', '1', file)
            with self.assertRaises(ValueError): check_index(release, file, 'test.gz')

    def test_package_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                check_package('Package: test\nVersion: 1\n\nPackage: test\nVersion: 1', 'test', '1', Path(tmp)/'none')


if __name__ == '__main__':
    unittest.main()
