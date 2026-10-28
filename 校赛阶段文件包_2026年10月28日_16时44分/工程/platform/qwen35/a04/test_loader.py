"""Loader metadata/path/hash rejects using retained local mutation fixtures."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
from quant.export_w4a8.loader import Sidecar
from quant.export_w4a8.core import weights,activations,shape
BASE=ROOT/'models/sidecar_A/qwen35-v1'
OUT=ROOT/'eval/qwen35/a04/loader-tests-v1'


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(exist_ok=False)
        cls.original=json.loads((BASE/'manifest.json').read_text())
    def fixture(self,name,mutate):
        d=OUT/name;d.mkdir();m=copy.deepcopy(self.original);mutate(m)
        with (d/'manifest.json').open('x') as f:json.dump(m,f)
        return d
    def test_valid_readonly(self):
        s=Sidecar(BASE);w,sw=s.load('l00_gate');self.assertFalse(w.flags.writeable);self.assertFalse(sw.flags.writeable)
    def test_metadata(self):
        mutations=[('schema',lambda m:m.update(schema='wrong')),('contract',lambda m:m.update(contract_sha256='0'*64)),
          ('revision',lambda m:m.update(source_revision='wrong')),('count',lambda m:m['entries'].pop()),
          ('duplicate',lambda m:m['entries'].__setitem__(1,m['entries'][0])),
          ('shape',lambda m:m['entries'][0].update(N=33)),('bias',lambda m:m['entries'][0].update(bias=True))]
        for name,mutation in mutations:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):Sidecar(self.fixture(name,mutation))
    def test_path(self):
        for i,path in enumerate(('../secret.bin','/tmp/secret.bin','C:\\secret.bin','x\\y','x:y')):
            d=self.fixture(f'path{i}',lambda m:m['entries'][0]['files']['w.bin'].update(file=path))
            with self.assertRaises(ValueError):Sidecar(d).load('l00_gate')
    def test_short_and_corrupt(self):
        for name in ('short','corrupt'):
            d=self.fixture(name,lambda m:None);e=self.original['entries'][0];fn=e['files']['w.bin']['file']
            raw=bytearray((BASE/fn).read_bytes())
            if name=='short':raw=raw[:-1]
            else:raw[0]^=1
            with (d/fn).open('xb') as f:f.write(raw)
            with self.assertRaises(ValueError):Sidecar(d).load(e['id'])
    def test_symlink(self):
        d=self.fixture('symlink',lambda m:None);name=self.original['entries'][0]['files']['w.bin']['file']
        (d/name).symlink_to(BASE/name)
        with self.assertRaises(ValueError):Sidecar(d).load('l00_gate')
    def test_bad_arrays(self):
        for x in (np.zeros((1,1),np.float64),np.zeros((0,1),np.float32),np.zeros((1,0),np.float32),np.zeros((1,4865),np.float32),np.zeros((1,1,1),np.float32)):
            with self.subTest(shape=x.shape,dtype=str(x.dtype)):
                with self.assertRaises(ValueError):weights(x)
                with self.assertRaises(ValueError):activations(x)
        with self.assertRaises(ValueError):activations(np.zeros((9,1),np.float32))
        for n,k in ((0,1),(True,1),(1,2**64-1),(4865,1)):
            with self.assertRaises(ValueError):shape(n,k)

if __name__=='__main__':unittest.main(verbosity=2)
