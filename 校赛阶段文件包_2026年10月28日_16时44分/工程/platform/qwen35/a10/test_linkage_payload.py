import base64
import gzip
from pathlib import Path
import tempfile
import unittest
import linkage_serial_payload as p


class LinkageTests(unittest.TestCase):
    def test_derived_receiver_compile_and_constraints(self):
        source=p.receiver_source()
        ns={'__name__':'test_receiver'}
        exec(compile(source,'derived-receiver','exec'),ns)
        self.assertEqual(ns['EXPECTED'],p.EXPECTED)
        self.assertEqual(ns['SIZE'],p.SIZE)
        self.assertEqual(ns['TARGET'].as_posix(),p.TARGET)
        self.assertIn(p.BOOT.encode(),source)
        self.assertIn(b'time.monotonic() + 30',source)
        self.assertNotIn(b'zocl.ko',source)
        self.assertIn(b"'a10-vadd-short').open('xb')",source)
    def test_wrong_source(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'wrong';f.write_bytes(b'not approved')
            with self.assertRaises(ValueError):p.prepare(f)
    def test_actual_approved_roundtrip_pc_only(self):
        root=Path(__file__).resolve().parents[3]
        binary=root/'platform/build/a10-vadd-short-20261018-v3/a10-vadd-short'
        plan=p.prepare(binary)
        ns={'__name__':'test_receiver'};exec(p.receiver_source(),ns)
        data=b''.join(ns['decode_chunk'](c['line'],i) for i,c in enumerate(plan['chunks']))
        self.assertEqual(ns['unpack'](data),binary.read_bytes())
        self.assertLessEqual(len(plan['command']),3500)
        self.assertEqual(plan['execution'],'NOT_PERFORMED')
    def test_no_overwrite_publication(self):
        ns={'__name__':'test_receiver'};exec(p.receiver_source(),ns)
        with tempfile.TemporaryDirectory() as t:
            path=Path(t);(path/'a10-vadd-short').write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):ns['publish'](path,b'anything')
            self.assertEqual((path/'a10-vadd-short').read_bytes(),b'preserve')


if __name__=='__main__':unittest.main(verbosity=2)
