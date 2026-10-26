import base64
import hashlib
import struct
import unittest
import zlib
from decode_boot_backup import decode_record


def fixture(script=b'echo fixture\n', kind=6, terminator=0):
    payload = struct.pack('>2I', len(script), terminator) + script
    header = struct.pack('>7I4B32s', 0x27051956, 0, 0, len(payload), 0, 0,
                         zlib.crc32(payload), 5, 22, kind, 0, b'fixture')
    header = header[:4] + struct.pack('>I', zlib.crc32(header)) + header[8:]
    return header + payload


def row(blob):
    return dict(kind='BOOT_SCRIPT_BACKUP', bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(),
                base64=base64.b64encode(blob).decode())


class BootBackupTests(unittest.TestCase):
    def test_valid_is_data_only(self):
        b = fixture(b'echo fixture; no_command_is_executed\n')
        self.assertEqual(decode_record(row(b)), (b, 'echo fixture; no_command_is_executed\n'))

    def test_sha_reject(self):
        r = row(fixture()); r['sha256'] = '0' * 64
        with self.assertRaises(ValueError): decode_record(r)

    def test_header_crc_reject(self):
        b = bytearray(fixture()); b[8] ^= 1
        with self.assertRaises(ValueError): decode_record(row(b))

    def test_payload_crc_reject(self):
        b = bytearray(fixture()); b[-1] ^= 1
        with self.assertRaises(ValueError): decode_record(row(b))

    def test_wrong_image_type(self):
        with self.assertRaises(ValueError): decode_record(row(fixture(kind=2)))

    def test_multiple_script_reject(self):
        with self.assertRaises(ValueError): decode_record(row(fixture(terminator=1)))

    def test_size_bound(self):
        with self.assertRaises(ValueError): decode_record(row(fixture(b'x' * 17000)))

    def test_bad_base64(self):
        r = row(fixture()); r['base64'] = '???'
        with self.assertRaises(ValueError): decode_record(r)


if __name__ == '__main__':
    unittest.main(verbosity=2)
