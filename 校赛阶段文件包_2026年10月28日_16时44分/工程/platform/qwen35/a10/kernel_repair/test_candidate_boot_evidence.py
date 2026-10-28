import base64
import hashlib
import json
import unittest
import zlib
from audit_candidate_boot_evidence import decode_log

class Evidence(unittest.TestCase):
    def fixture(self):
        raw=b"Linux version test\n"
        return raw,dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                        zlib_base64=base64.b64encode(zlib.compress(raw)).decode())
    def test_verified_roundtrip(self):
        raw,row=self.fixture()
        self.assertEqual(decode_log(json.dumps(row)),raw)
    def test_corrupted_hash_or_length(self):
        for k,v in (("bytes",1),("sha256","0"*64)):
            _,row=self.fixture();row[k]=v
            with self.assertRaises(ValueError):decode_log(json.dumps(row))
    def test_ambiguous_or_trailing(self):
        _,row=self.fixture();text=json.dumps(row)
        with self.assertRaises(ValueError):decode_log(text+"\n"+text)
        row["zlib_base64"]=base64.b64encode(base64.b64decode(row["zlib_base64"])+b"x").decode()
        with self.assertRaises(ValueError):decode_log(json.dumps(row))
if __name__=="__main__":unittest.main()
