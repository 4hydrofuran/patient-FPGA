"""Read-only placed-layout fixtures, no device/owner or ARM execution."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from resident_evidence import OUT,ROOT,read,sha
from resident_board_prepare import relocate


class RelocationTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory(prefix='resident-relocation-');self.addCleanup(temp.cleanup)
        root=Path(temp.name);b=read(OUT/'BOARD_BUILD-v1-review-only.json')
        assets={'prefix_template','kernel_source','xclbin','resident_policy','chat_template'}
        for dirname in ('assets','bin','resident-app','ordinary-resource-probe'):(root/dirname).mkdir()
        policy=read(b['resident_policy'])
        for i,row in enumerate(b['runtime_artifacts']+b['auxiliary_artifacts']):
            target=root/('assets' if row['role'] in assets else 'bin')/Path(row['path']).name
            target.write_bytes(Path(row['path']).read_bytes() if row['role']=='resident_policy' else ('SMALL_LAYOUT_FIXTURE_'+str(i)).encode())
            row['sha256']=sha(target)
        for row in policy['files']:
            target=root/'resident-app'/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((Path(b['resident_app'])/row['path']).read_bytes())
        for alias in b['loader_aliases']:
            target=root/'bin'/alias['target_basename'];alias['sha256']=sha(target)
            link=root/'bin'/alias['name']
            if link!=target:link.symlink_to(target.name)
        source=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2/manifest.json'
        shutil.copyfile(source,root/'ordinary-resource-probe/manifest.json')
        return root,b

    def test_placed_layout_and_policy(self):
        root,b=self.fixture();old=copy.deepcopy(b);r=relocate(b,root)
        self.assertEqual(old,b);self.assertFalse(r['authorization_included'])
        self.assertEqual(r['resident_app'],str(root/'resident-app'))
        self.assertFalse(r['relocation_required'])
        self.assertEqual(r['native_asset_root'],'/opt/patient-qwen')

    def test_tampered_application(self):
        root,b=self.fixture();(root/'resident-app/app/session.py').write_text('CHANGED')
        with self.assertRaises(RuntimeError):relocate(b,root)

    def test_changed_backend(self):
        root,b=self.fixture();(root/'bin'/Path(b['backend_library']).name).write_text('CHANGED')
        with self.assertRaises(RuntimeError):relocate(b,root)

    def test_symlink_payload(self):
        root,b=self.fixture();target=root/'bin'/Path(b['native']).name
        other=root/'outside';target.rename(other);target.symlink_to(other)
        with self.assertRaises(RuntimeError):relocate(b,root)

    def test_old_baseline_manifest_required(self):
        root,b=self.fixture();(root/'ordinary-resource-probe/manifest.json').write_text('CHANGED')
        with self.assertRaises(RuntimeError):relocate(b,root)


if __name__=='__main__':unittest.main()
