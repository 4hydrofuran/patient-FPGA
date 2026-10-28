"""Small relocation fixtures only: no model, ARM execution or Board access."""
import copy
from pathlib import Path
import tempfile
from plmode_evidence import OUT,BUNDLE,read,save,sha
from plmode_runtime import relocate

def refuses(call):
    try:call()
    except (RuntimeError,FileNotFoundError):return
    raise AssertionError('changed/incomplete relocation accepted')

def main():
    prepared=read(OUT/'BOARD_BUILD-v2-complete.json');tests=[]
    with tempfile.TemporaryDirectory(prefix='a12-relocation-fixture-') as d:
        root=Path(d);(root/'bin').mkdir();(root/'assets').mkdir();(root/'ordinary-resource-probe').mkdir()
        # Replace large external artifacts with tiny explicit fixture bytes.
        b=copy.deepcopy(prepared)
        for i,row in enumerate(b['runtime_artifacts']+b['auxiliary_artifacts']):
            path=root/('assets' if row['role'] in ('prefix_template','kernel_source','xclbin') else 'bin')/Path(row['path']).name
            path.write_bytes(('PC_RELOCATION_FIXTURE_'+str(i)).encode());row['sha256']=sha(path)
        for alias in b['loader_aliases']:
            target=root/'bin'/alias['target_basename'];alias['sha256']=sha(target)
            path=root/'bin'/alias['name']
            if path!=target:path.symlink_to(target.name)
        (root/'ordinary-resource-probe/manifest.json').write_bytes((BUNDLE/'manifest.json').read_bytes())
        before=copy.deepcopy(b);result=relocate(b,root);assert result['asset_root']==str(root) and b==before
        tests.append('ALREADY_PLACED_FIXTURE_LAYOUT_AND_SONAME_ALIASES')
        alias=next(r for r in b['loader_aliases'] if r['name']!=r['target_basename']);path=root/'bin'/alias['name'];path.unlink()
        refuses(lambda:relocate(b,root));tests.append('MISSING_SONAME_REJECTED');path.symlink_to(alias['target_basename'])
        target=root/'bin'/alias['target_basename'];original=target.read_bytes();target.write_bytes(b'CHANGED')
        refuses(lambda:relocate(b,root));tests.append('CHANGED_ARTIFACT_REJECTED');target.write_bytes(original)
        row=b['runtime_artifacts'][0];path=root/'bin'/Path(row['path']).name;original=path.read_bytes();path.unlink();other=root/'linked-native';other.write_bytes(original);path.symlink_to(other)
        refuses(lambda:relocate(b,root));tests.append('SYMLINK_RUNTIME_PAYLOAD_REJECTED');path.unlink();path.write_bytes(original)
        manifest=root/'ordinary-resource-probe/manifest.json';manifest.write_bytes(b'CHANGED')
        refuses(lambda:relocate(b,root));tests.append('CHANGED_ORDINARY_MANIFEST_REJECTED')
    save(OUT/'RELOCATION_TEST.json',dict(status='PASS_READONLY_RELOCATION_FIXTURES',tests=tests,count=len(tests),model_copied=False,ARM_execution='NOT_EXECUTED',BOARD='NOT_TESTED'))
    print('PASS_READONLY_RELOCATION_FIXTURES',len(tests))
if __name__=='__main__':main()
