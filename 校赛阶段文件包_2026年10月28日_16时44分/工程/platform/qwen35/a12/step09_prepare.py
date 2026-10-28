"""Freeze task09 scope and derive isolated controllers; no board side effects."""
import ast,json,shutil
from common import ROOT,sha,save
from step09_common import OUT

def replace(s,a,b):
    assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)

if __name__=='__main__':
    before=OUT/'before'
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md'):
        p=before/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    base=dict(op='generate',tokens=list(range(1,10)),teacher_tokens=[10,11],max_tokens=2,state_fingerprint=True,prefill_chunk=8)
    short=[dict(base,id='short_t'+str(t),prefill_chunk=t,logits_mode='all',diagnostic=True,a12_consumer_trace=True) for t in (1,2,4,8)]
    short += [dict(op='reset',id='reset_A'),dict(base,id='case_B',tokens=list(range(9,0,-1))),dict(base,id='reject_R1',cache_policy='R1'),dict(base,id='reject_R2',cache_policy='R2'),dict(base,id='A_after_B_rejects'),dict(base,id='cancel_boundary',max_tokens=64,teacher_tokens=[],cancel_test=True)]
    long_tokens=([1,2,3,4,5,6,7,8,9]*114)[:1022]
    context=[dict(base,id='A_after_cancel_new_window'),dict(base,id='context1024_chunk8',tokens=long_tokens,prefill_chunk=8,save_logits_reference=True),dict(base,id='context1024_chunk256',tokens=long_tokens,prefill_chunk=256,compare_logits=True)]
    save(OUT/'REQUESTS.json',dict(short=short,context=context))
    # Cancel at the next serialized submit boundary, after 72 successful synchronous calls.
    # CPU cancellation is after first native token; it has no PL permit lane.
    budgets={}
    for variant,runs,seconds in [('short',4000,7200),('context',20000,14400)]:
        budget=dict(schema='A12_STEP09_BOUNDED_V1',physical_domain='BOARD',context=1024,physical_ubatch=8,
          per_request_receive_timeout_seconds=5400,profiles=[dict(scope='all',max_successful_runs=runs,weight_load_limit=72,explicit_bo_limit_bytes=140591104,request_limit=len(short if variant=='short' else context),prompt_token_limit=128 if variant=='short' else 1022,output_token_limit=64 if variant=='short' else 2,max_session_seconds=seconds)])
        save(OUT/(variant+'-budget.json'),budget);budgets[variant]=budget
    save(OUT/'SCOPE.json',dict(status='FROZEN_BEFORE_COMPUTE',default_context_source='system_qwen35/app/default_e2e/policy.py:profile',default_context=1024,requests_sha256=sha(OUT/'REQUESTS.json'),budgets=budgets,cancellation='after confirmed synchronous completion before next submit; deny subsequent permits; SIGUSR1, no kill; discard terminal result; close normally; next request only fresh worker/window',R0='clear all recurrent/conv/KV before and after every generate',R1_R2='disabled',fallback='disabled',BOARD_dangerous_timeout_poison='NOT_TESTED',extension2048='NOT_TESTED_SEPARATE',major_unresolved_limit_seconds=600,actual_model_settings='unknown'))
    p=ROOT/'platform/qwen35/a12'
    s=(p/'step07_supervisor.py').read_text();s=replace(s,"self.health();phase=r['phase'];closing=phase=='router_close'","self.health();phase=r['phase'];closing=phase=='router_close'\n                    hook=getattr(self,'before_permission',None)\n                    if hook:hook(r)")
    (p/'step09_supervisor.py').write_text(s,encoding='utf-8',newline='\n')
    s=(p/'window_closeout_v2.py').read_text();s=replace(s,'from step07_supervisor import OwnedWorker','from step09_supervisor import OwnedWorker')
    (p/'step09_window.py').write_text(s,encoding='utf-8',newline='\n')
    s=(p/'step08_manager.py').read_text();s=replace(s,'from window_closeout_v2 import Window','from step09_window import Window')
    begin=s.index('def run_case(');end=s.index('\n\ndef main():',begin)
    s=s[:begin]+(p/'step09_cases.py').read_text()+s[end:]
    s=s.replace("step08='IN_PROGRESS_'","step09='IN_PROGRESS_'")
    (p/'step09_manager.py').write_text(s,encoding='utf-8',newline='\n')
    for name in ('step09_supervisor.py','step09_window.py','step09_manager.py'):ast.parse((p/name).read_text())
    print('TASK09_SCOPE_AND_DERIVED_CONTROLLERS_READY')
