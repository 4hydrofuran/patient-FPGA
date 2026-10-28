import base64
import gzip
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('payload',Path(__file__).with_name('driver_serial_payload.py'))
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PayloadTests(unittest.TestCase):
    def test_order_and_base64(self):
        self.assertEqual(p.decode_chunk('0:'+base64.b64encode(b'abc').decode(),0),b'abc')
        for line,seq in [('0:YWJj',1),('0:?',0),('0:',0),('0:'+base64.b64encode(b'a'*769).decode(),0)]:
            with self.assertRaises(ValueError):p.decode_chunk(line,seq)

    def test_unpack_bound_hash(self):
        expected=b'hello'
        payload=gzip.compress(expected)
        self.assertEqual(p.unpack(payload,hashlib.sha256(expected).hexdigest(),5),expected)
        for digest,size in [('0'*64,5),(hashlib.sha256(expected).hexdigest(),4)]:
            with self.assertRaises(ValueError):p.unpack(payload,digest,size)
        with self.assertRaises(ValueError):p.unpack(b'x'*(p.MAX_COMPRESSED+1))

    def test_bad_gzip(self):
        with self.assertRaises((OSError,EOFError)):p.unpack(b'bad')

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'zocl.ko';f.write_bytes(b'original')
            with self.assertRaises(FileExistsError):p.publish(Path(folder),b'new')
            self.assertEqual(f.read_bytes(),b'original')

    def test_reject_wrong_source(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'ko';f.write_bytes(b'wrong')
            with self.assertRaises(ValueError):p.prepare(f)

    def test_real_candidate_roundtrip_pc_only(self):
        root=Path(__file__).resolve().parents[3]
        source=root/'platform/local/a10-xrt-2.18-audit/zocl-2.18-stripped-PC_ONLY.ko'
        if not source.exists():self.skipTest('Fixed candidate not present')
        plan=p.prepare(source)
        compressed=b''.join(p.decode_chunk(c['line'],i) for i,c in enumerate(plan['chunks']))
        self.assertEqual(p.unpack(compressed),source.read_bytes())
        self.assertLessEqual(len(plan['command']),3500)


if __name__=='__main__':unittest.main(verbosity=2)
