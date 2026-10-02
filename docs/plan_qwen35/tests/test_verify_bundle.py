import unittest, tempfile, json, hashlib, importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('verify', ROOT/'tools/verify_bundle.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class BundleTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.lock=ROOT/'contracts/contract_lock.json'
  contract=json.loads(self.lock.read_text())['contract_sha256']
  for name in ['selftest.py','worker.py','report.txt']:(self.root/name).write_text('TEST FIXTURE ONLY')
  self.m={'schema_version':1,'module_type':'voice','module_id':'test_fixture','contract_sha256':contract,
   'source_commit':'fixture-not-project','entrypoints':{'selftest':'selftest.py','worker':'worker.py'},
   'tests':{'pc':{'status':'PASS','evidence':['report.txt']},'board':{'status':'NOT_TESTED','evidence':[]}},
   'board_identity':None,'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in self.root.iterdir()]}
  self.save()
 def save(self):(self.root/'manifest.json').write_text(json.dumps(self.m))
 def tearDown(self):self.tmp.cleanup()
 def test_valid(self):self.assertEqual(v.check_bundle(self.root,self.lock)['static_integrity'],'PASS')
 def test_no_board(self):
  with self.assertRaises(ValueError):v.check_bundle(self.root,self.lock,True)
 def test_wrong_contract(self):
  self.m['contract_sha256']='0'*64;self.save()
  with self.assertRaises(ValueError):v.check_bundle(self.root,self.lock)
 def test_tamper(self):
  (self.root/'worker.py').write_text('bad')
  with self.assertRaises(ValueError):v.check_bundle(self.root,self.lock)
 def test_undeclared(self):
  (self.root/'secret.txt').write_text('bad')
  with self.assertRaises(ValueError):v.check_bundle(self.root,self.lock)
 def test_traversal(self):
  self.m['files'][0]['path']='../outside';self.save()
  with self.assertRaises(ValueError):v.check_bundle(self.root,self.lock)
 def test_symlink(self):
  (self.root/'extra').symlink_to(self.root/'worker.py')
  with self.assertRaises(ValueError):v.check_bundle(self.root,self.lock)
 def test_false_pass(self):
  self.m['tests']['board']={'status':'PASS','evidence':[]};self.save()
  with self.assertRaises(ValueError):v.check_bundle(self.root,self.lock)
if __name__=='__main__':unittest.main()
