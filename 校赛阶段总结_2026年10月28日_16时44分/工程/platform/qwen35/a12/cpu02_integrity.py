"""Protect the frozen CPU01 implementation and prove CPU02 mutation boundaries."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'
PRIOR=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'
BASE=PRIOR/'integrated/bundle-v1'


def j(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def definitions(text):
    tree=ast.parse(text);result={}
    for n in tree.body:
        if isinstance(n,ast.FunctionDef):result[n.name]=ast.dump(n,include_attributes=False)
        if isinstance(n,ast.ClassDef):
            for m in n.body:
                if isinstance(m,ast.FunctionDef):result[n.name+'.'+m.name]=ast.dump(m,include_attributes=False)
    return result


if __name__=='__main__':
    seal=j(PRIOR/'SEAL.json')
    for name,row in seal['files'].items():
        p=PRIOR/name;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],name
    changed={}
    allowed={'cpu01b_supervisor_base.py':{'OwnedWorker.record','OwnedWorker.close'},'cpu01b_health.py':{'PersistentKmsg.drain'},'cpu01b_kernel_gate.py':{'MinimalGate.observe_action'},'cpu01b_window.py':{'WindowBase.owner_check'},'cpu01b_healthrecord.py':{'compact_kernel_record'}}
    for path in (OUT/'source').glob('cpu01b_*.py'):
        a=definitions((BASE/'platform/qwen35/a12'/path.name).read_text(encoding='utf-8'));b=definitions(path.read_text(encoding='utf-8'))
        assert a.keys()==b.keys();diff={key for key in a if a[key]!=b[key]}
        assert diff==allowed.get(path.name,set()),(path.name,diff)
        changed[path.name]=sorted(diff)
    # In particular the permission order, budgets, fresh callbacks, record-before-
    # reply and failure handler are exact unchanged AST, not merely unit-test doubles.
    for mode in ('baseline','candidate'):
        root=OUT/mode/'bundle-v1'
        for row in j(root/'manifest.json')['files']:
            p=root/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        for row in j(BASE/'manifest.json')['files']:
            name=row['path']
            if name.startswith(('bin/','source/','hardware/','control/support/')):assert sha(root/name)==row['sha256'],name
    with (OUT/'INTEGRITY.json').open('x',encoding='utf-8') as stream:
        json.dump(dict(status='PASS_CPU02_SCOPE_AND_CPU01_SEAL',cpu01_sealed_files=len(seal['files']),cpu01_seal_sha256=sha(PRIOR/'SEAL.json'),changed_methods=changed,
            permission_protocol_budget_fresh_callbacks_record_before_reply_failure_handler='UNCHANGED_AST',normal_platform_recovery='UNCHANGED_AST',
            all_native_binary_library_model_math_task01A_task03_and_shared_support='UNCHANGED_BYTES',CROSS_BUILD='NOT_REQUIRED_PYTHON_ONLY_REUSED_A53_HASH_PINNED'),stream,indent=2);stream.write('\n')
    print('PASS_CPU02_SCOPE_AND_CPU01_SEAL')
