import copy
import json
from pathlib import PureWindowsPath
import unittest
from upload_candidate import REMOTE
from verify_upload_diagnosis import validate

class Paths(unittest.TestCase):
    def test_remote_posix_on_windows(self):
        self.assertEqual(PureWindowsPath("/home/ubuntu/a10-kernel-trial-20261020-v1").as_posix(), REMOTE)
        self.assertEqual(REMOTE, "/home/ubuntu/a10-kernel-trial-20261020-v1")
        self.assertNotIn("\\", REMOTE)

    def fixture(self):
        row = dict(path=REMOTE,symlink=False,directory=True,
                   files=[dict(name="x",sha256="a",symlink=False)])
        return dict(hashes={"x":"a"}), dict(exit_code=0,board_writes=False,stdout=json.dumps([row]))

    def test_verified_readback(self):
        a,b=self.fixture()
        self.assertEqual(validate(a,b)["status"],"UPLOADED_HASH_VERIFIED_NOT_INSTALLED")

    def test_mismatch_or_link_or_wrong_target(self):
        a,b=self.fixture()
        for field,value in (("path",REMOTE+"x"),("symlink",True),("directory",False)):
            c=copy.deepcopy(b);rows=json.loads(c["stdout"]);rows[0][field]=value;c["stdout"]=json.dumps(rows)
            with self.assertRaises(ValueError):validate(a,c)
        a["hashes"]["x"]="bad"
        with self.assertRaises(ValueError):validate(a,b)

if __name__=="__main__":unittest.main()
