import unittest, struct, json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Contracts(unittest.TestCase):
 def test_hand(self):
  w=(ROOT/'fixtures/w_packed.bin').read_bytes();x=(ROOT/'fixtures/xq.bin').read_bytes()
  self.assertEqual((w[0],w[16]),(0x97,0x2f));self.assertEqual(x[:2],bytes([127,255]))
  y=struct.unpack('<32f',(ROOT/'fixtures/expected_y.bin').read_bytes())
  self.assertEqual(y[:2],(890.0,-891.0));self.assertTrue(all(v==0 for v in y[2:]))
 def test_fixture_hashes(self):
  m=json.loads((ROOT/'fixtures/hand_sample.json').read_text())
  for p,h in m['files'].items():self.assertEqual(hashlib.sha256((ROOT/'fixtures'/p).read_bytes()).hexdigest(),h)
 def test_shapes(self):
  q=json.loads((ROOT/'contracts/quant_v1.json').read_text())
  self.assertEqual(q['target_shapes'][0],{'kind':'gate_up','N':3584,'K':1024})
  for s in q['target_shapes']:
   self.assertLessEqual(s['N'],4864);self.assertLessEqual(s['K'],4864)
 def test_lock(self):
  m=json.loads((ROOT/'contracts/contract_lock.json').read_text())
  self.assertEqual(hashlib.sha256(json.dumps(m['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),m['contract_sha256'])
  for p,h in m['files'].items():self.assertEqual(hashlib.sha256((ROOT/'contracts'/p).read_bytes()).hexdigest(),h)
if __name__=='__main__':unittest.main()
