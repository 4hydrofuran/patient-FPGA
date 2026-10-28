"""Exact primary-package verifier: nested manifest and rejection fixtures, PC only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from common import ROOT

tool=ROOT/'docs/plan_qwen35/KV260_Qwen35_A_详细设计增强任务包_20261002/KV260_Qwen35_A_设计增强包_20261002/tools/verify_bundle.py'
spec=importlib.util.spec_from_file_location('primary_verifier',tool);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'nested').mkdir();(self.root/'nested/manifest.json').write_text('{}')
        (self.root/'selftest.py').write_text('# static fixture, never executed\n')
        entries=[dict(path=p.relative_to(self.root).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in self.root.rglob('*') if p.is_file()]
        self.manifest=dict(schema_version=1,module_type='linear',module_id='PC_FIXTURE',source_commit='PC_FIXTURE',
          contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',files=entries,
          entrypoints=dict(library='nested/manifest.json',selftest='selftest.py'),tests=dict(board=dict(status='NOT_TESTED',evidence=[])))
        self.write()
    def write(self):(self.root/'manifest.json').write_text(json.dumps(self.manifest))
    def check(self,**kw):return module.check_bundle(self.root,ROOT/'contracts/qwen35/contracts.lock',**kw)
    def tearDown(self):self.tmp.cleanup()
    def test_declared_nested_manifest_accepted(self):self.assertEqual(self.check()['static_integrity'],'PASS')
    def test_undeclared_nested_manifest_rejected(self):
        self.manifest['files']=[e for e in self.manifest['files'] if e['path']!='nested/manifest.json'];self.write()
        with self.assertRaises(ValueError):self.check()
    def test_changed_payload_rejected(self):
        (self.root/'nested/manifest.json').write_text('{"changed":true}')
        with self.assertRaises(ValueError):self.check()
    def test_static_pass_cannot_claim_board(self):
        with self.assertRaises(ValueError):self.check(require_board=True)


if __name__=='__main__':unittest.main()
