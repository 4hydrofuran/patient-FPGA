"""Pre-execution scope revision: include real frozen synthetic case A/B prompts."""
import json
from common import ROOT,sha,save
from step09_common import OUT

if __name__=='__main__':
    def j(p):return json.loads(p.read_text(encoding='utf-8'))
    assert not (OUT/'short').exists()
    old=OUT/'REQUESTS.json';requests=j(old);old.rename(OUT/'REQUESTS-v1-synthetic-only.json')
    dev=j(ROOT/'evidence/model_pl_A/20261024-step08-v1/TOKENIZED_REQUESTS.json')['generation']
    case=[]
    for i,name in [(0,'medical_A'),(1,'medical_B'),(0,'medical_A_again')]:
        source=dev[i];case.append(dict(id=name,op='generate',prompt=source['prompt'],tokens=source['tokens'],max_tokens=2,teacher_tokens=[10,11],prefill_chunk=8,state_fingerprint=True))
    requests['short'][-1:-1]=case;save(old,requests)
    p=OUT/'short-budget.json';budget=j(p);p.rename(OUT/'short-budget-v1.json')
    budget['profiles'][0].update(max_successful_runs=6000,request_limit=len(requests['short']))
    save(p,budget)
    p=OUT/'SCOPE.json';scope=j(p);p.rename(OUT/'SCOPE-v1.json')
    scope['requests_sha256']=sha(old);scope['budgets']['short']=budget
    scope['revision']='v2 before any board compute: add DEV-001/DEV-002 real frozen synthetic case prompts and replay; unchanged math/thresholds'
    save(p,scope)
    p=ROOT/'platform/qwen35/a12';s=(p/'step09_manager.py').read_text();begin=s.index('def run_case(');end=s.index('\n\ndef main():',begin)
    (p/'step09_manager.py').write_text(s[:begin]+(p/'step09_cases.py').read_text()+s[end:],encoding='utf-8',newline='\n')
    print('TASK09_PRE_EXECUTION_REAL_CASE_SCOPE_V2')
