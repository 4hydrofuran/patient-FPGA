"""Freeze full-model diagnostic and all 24 existing development questions."""
import json
import shutil
import sys
from jinja2.sandbox import ImmutableSandboxedEnvironment
from common import ROOT,sha,save
from step08_common import OUT
sys.path.insert(0,str(ROOT))
from system_qwen35.app.domain import load_case,Transcript
from system_qwen35.app.planning import plan
from system_qwen35.app.checking import prompt_messages,fallback
from budget import budget

def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
                 'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md'):
        p=OUT/'before'/name;p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists():assert p.read_bytes()==(ROOT/name).read_bytes()
        else:shutil.copyfile(ROOT/name,p)
    template=ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja'
    env=ImmutableSandboxedEnvironment();render=env.from_string(template.read_text(encoding='utf-8'))
    dev=ROOT/'eval/qwen35/a02/dev/questions-v2.json';rows=j(dev);assert len(rows)==24
    requests=[];policies=[];facts=[]
    for row in rows:
        case=load_case(row['case_id'])
        t=Transcript.parse(dict(request_id=row['id'],text=row['question'],source='typed',final=True))
        p=plan(case,t,[])
        assert p.route==row['expected_route'],row
        if p.route!='answer':
            policies.append(dict(id=row['id'],question=row['question'],route=p.route,text=fallback(p),case_id=row['case_id'],source='POLICY_TEMPLATE_NO_MODEL'))
            continue
        messages=prompt_messages(p,row['question'])
        prompt=render.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
        assert prompt.endswith('<think>\n\n</think>\n\n')
        requests.append(dict(id=row['id'],op='generate',prompt=prompt,max_tokens=24,logits_mode='final',prefill_chunk=256,
           cache_policy='R0',state_fingerprint=True,a12_consumer_trace=False))
        facts.append(dict(id=row['id'],case_id=row['case_id'],question=row['question'],case_sha256=case.sha256,
           expected_intents=row['expected_intents'],expected_route=p.route,messages=messages))
    assert len(requests)==17 and len(policies)==7
    diag=j(ROOT/'evidence/model_pl_A/20261023-step06-v1/requests.json')[0];diag.pop('diagnostic')
    diag.update(diagnostic_all_layers=True,diagnostic_nodes=True,diagnostic_report=True,state_fingerprint=True,
       dump_state=True,a12_consumer_trace=True)
    save(OUT/'REQUESTS.json',dict(diagnostic=[diag],generation=requests,policy_only=policies,answer_facts=facts,
       source_sha256=sha(dev),template_sha256=sha(template),medical_review='PENDING_NOT_CLAIMED',
       generation_mode='Normal final logits; no per-call native consumer ledger to avoid diagnostic quadratic copies'))
    entries=j(ROOT/'models/sidecar_A/qwen35-v1/manifest.json')['entries']
    for name,output,count,seconds in [('diagnostic',2,1,360),('generation',24,17,1200)]:
        b=budget(entries,'all',prompt=128,output=output,requests=count);b['max_session_seconds']=seconds
        save(OUT/(name+'-budget.json'),dict(status='REVIEWED_NEW_PRIVATE_STEP08_BOUND_NOT_PUBLIC_MATH_CHANGE',profiles=[b],
           rationale='Same full BO,72loads; explicit per-request token/request and total run limits. Deadline includes CPU pairing and guarded hardware calls; no forced exit on expiry.',
           per_request_receive_timeout_seconds=240 if name=='diagnostic' else 120,
           original_120_second_budget='PRESERVED_IN_PARENT_NOT_SILENTLY_REUSED',
           fresh_resource_gate=dict(CmaFree_kib=98304,MemAvailable_kib=1114112)))
    p=ROOT/'platform/qwen35/a12/step08_transport.py'
    p.write_text((ROOT/'platform/qwen35/a12/step07_transport.py').read_text(encoding='utf-8').replace('A12_STEP07_SINGLE_PROJECTION_AUTHORIZED','A12_STEP08_FULL_MODEL_AUTHORIZED'),encoding='utf-8',newline='\n')
    save(OUT/'SCOPE.json',dict(scope='all_24_layers_72_projections',diagnostic_requests=1,development_questions=24,
       model_requests=17,policy_templates=7,diagnostic_budget=1224,generation_budget=47736,
       explicit_BO_bytes=140591104,weight_loads_per_window=72,step09='NOT_STARTED',subagents=0,
       math_changed=False,tolerances_changed=False,model_settings='unknown'))
    print('STEP08_REQUESTS_AND_EXPLICIT_WINDOW_BUDGETS_FROZEN')
