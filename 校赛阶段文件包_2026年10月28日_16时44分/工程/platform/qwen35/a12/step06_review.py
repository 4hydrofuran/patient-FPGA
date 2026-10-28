"""Check UTF-8 artifacts, governance consistency and bounded scope before seal."""
import ast
import json
from common import ROOT
from step06_prepare import OUT


def main():
    count=0
    for p in OUT.rglob('*.json'):
        json.loads(p.read_text(encoding='utf-8'));count+=1
    for p in (ROOT/'platform/qwen35/a12').glob('step06_*.py'):
        ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    audit=json.loads((OUT/'AUDIT.json').read_text(encoding='utf-8'))
    assert audit['natural']['text']=='胸口疼。' and audit['natural']['eos']
    assert audit['cross_ISA_graph_status'].startswith('FAIL')
    assert not audit['initial_admission']['all']['reserve_check']
    assert all(x['reserve_check'] for x in audit['admission'].values())
    old=json.loads((OUT/'before/docs/PROJECT_STATUS.json').read_text(encoding='utf-8'))
    new=json.loads((ROOT/'docs/PROJECT_STATUS.json').read_text(encoding='utf-8'))
    for key,value in old.items():
        if key not in ('stage','stage_status'):assert new[key]==value,key
    assert new['a12_step06_20261023']['hardware_submissions']==0
    plan=(ROOT/'docs/A12_STEP_PLAN_20261023.md').read_text(encoding='utf-8')
    assert plan[plan.index('### 06｜'):plan.index('### 07｜')].count('- [x]')==4
    assert '- [x]' not in plan[plan.index('### 07｜'):plan.index('## 5.')]
    # The final audit explicitly decodes every JSON text read on Windows.
    tree=ast.parse((ROOT/'platform/qwen35/a12/step06_audit.py').read_text(encoding='utf-8'))
    reads=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='read_text']
    assert reads and all(any(k.arg=='encoding' and k.value.value=='utf-8' for k in n.keywords) for n in reads)
    print(json.dumps(dict(status='PASS_UTF8_AND_STAGE06_SCOPE',JSON_files=count,explicit_UTF8_audit_reads=len(reads),historical_status_fields_preserved=True,step07_started=False)))


if __name__=='__main__':main()
