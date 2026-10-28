import struct
import tempfile
import unittest
from pathlib import Path
from audit_module_stage import MARKER, split_signature, required_signature, module_paths


class StageTests(unittest.TestCase):
    def test_unsigned(self):
        self.assertEqual(split_signature(b'ELF'), (b'ELF', None))

    def test_signature_split(self):
        raw = b'ELF' + b'sig' + bytes([0, 0, 2, 0, 0, 0, 0, 0]) + struct.pack('>I', 3) + MARKER
        self.assertEqual(split_signature(raw), (b'ELF', b'sig'))

    def test_bad_signatures(self):
        for raw in (MARKER, b'ELF' + bytes(12) + MARKER,
                    b'ELF' + bytes([0,0,2,0,0,0,0,0]) + struct.pack('>I', 1000) + MARKER):
            with self.assertRaises(ValueError):
                split_signature(raw)

    def test_vendor_policy(self):
        self.assertTrue(required_signature('kernel/drivers/net/a.ko', set()))
        self.assertFalse(required_signature('kernel/drivers/staging/a.ko', set()))
        self.assertTrue(required_signature('kernel/drivers/staging/a.ko', {'a.ko'}))

    def test_unexpected_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'signing_key.pem').write_text('fixture-not-a-key')
            with self.assertRaisesRegex(ValueError, 'Unexpected staged file'):
                module_paths(root)

    def test_links_never_followed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'a.ko').write_bytes(b'fixture')
            (root/'build').symlink_to('/nonexistent/private-key-tree')
            paths, excluded = module_paths(root)
            self.assertEqual([p.name for p in paths], ['a.ko'])
            self.assertEqual(excluded, ['build'])
            (root/'escape.ko').symlink_to('/nonexistent/module')
            with self.assertRaisesRegex(ValueError, 'Unexpected module-tree symlink'):
                module_paths(root)


if __name__ == '__main__':
    unittest.main()
