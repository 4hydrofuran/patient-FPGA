"""Validate unchanged sealed baselines and exact integration/package boundaries."""
import ast
import hashlib
import json
from pathlib import Path
import difflib

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'


def j(path):return json.loads(path.read_text(encoding='utf-8'))
def pin(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    seals={}
    for name in ('20261024-health-opt-v1','20261024-cpu-opt-00-v1','20261024-cpu-opt-01b-v1','20261024-cpu-peer01a-review-v1'):
        directory=ROOT/'evidence/model_pl_A'/name;seal=j(directory/'SEAL.json')
        for relative,row in seal['files'].items():
            path=directory/relative;assert path.stat().st_size==row['bytes'] and pin(path)==row['sha256'],str(path)
        seals[name]=dict(seal_sha256=pin(directory/'SEAL.json'),unchanged_files=len(seal['files']))
    old=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1/source'
    source=OUT/'manager-source'
    for p in old.glob('*.py'):assert pin(p)==pin(source/p.name)
    before=(old/'cpu01b_manager.py').read_text(encoding='utf-8');after=(source/'cpu01_manager.py').read_text(encoding='utf-8')
    (OUT/'manager.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='cpu01b_manager.py',tofile='cpu01_manager.py')),encoding='utf-8')
    definitions=lambda text:{n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
    a,b=definitions(before),definitions(after)
    assert a.keys()==b.keys()
    assert [k for k in a if a[k]!=b[k]]==['run_case']
    for mode in ('old','integrated'):
        root=OUT/mode/'bundle-v1'
        for row in j(root/'manifest.json')['files']:
            p=root/row['path'];assert p.stat().st_size==row['bytes'] and pin(p)==row['sha256']
        base=ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-bundle'
        for row in j(base/'manifest.json')['files']:
            name=row['path']
            if name.startswith(('bin/','hardware/')) and name!='bin/qwen35-a12':assert pin(root/name)==row['sha256']
    result=dict(status='PASS_OLD_SEALS_AND_PACKAGE_BOUNDARIES',seals=seals,unchanged_01b_modules=len(list(old.glob('*.py'))),
        original_manager_changed_definitions=['run_case'],manager_change='bounded exact diagnostic before normal cases; strict V1/V2 reader; worker counters; numerical comparison. Platform/owner/recovery/receive/BO validation unchanged AST.',
        runtime_libraries_hardware_and_public_contracts_unchanged=True,task03_changed=False,peer_original_changed=False)
    with (OUT/'INTEGRITY.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))


if __name__=='__main__':main()
