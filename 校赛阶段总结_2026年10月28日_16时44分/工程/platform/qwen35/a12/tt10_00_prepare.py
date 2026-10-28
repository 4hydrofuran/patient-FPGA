"""Freeze real routed prompts and tokenize with the pinned PC native runtime."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-ttft10-00-v1'
sys.path.insert(0,str(ROOT))
from jinja2.sandbox import ImmutableSandboxedEnvironment
from system_qwen35.app.domain import load_case,Transcript
from system_qwen35.app.planning import plan
from system_qwen35.app.checking import prompt_messages
from supervisor import OwnedWorker


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def j(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def lcp(a,b):
    n=0
    for x,y in zip(a,b):
        if x!=y:break
        n+=1
    return n


def main():
    template_path=ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja'
    template=template_path.read_text(encoding='utf-8');env=ImmutableSandboxedEnvironment()
    old=j(ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/inputs/development17.json')
    dev=j(ROOT/'eval/qwen35/a02/dev/questions-v2.json')
    variants=[('V01','SYN_CP_01','疼痛位置在哪里？'),('V02','SYN_CP_02','胸痛的性质是什么？'),
              ('V03','SYN_CP_03','胸痛每次持续多久？'),('V04','SYN_CP_01','疼痛有几分？'),
              ('V05','SYN_CP_03','有没有气短？'),('V06','SYN_CP_02','有没有药物过敏？'),
              ('V07','SYN_CP_01','什么情况下胸痛会加重？'),('V08','SYN_CP_02','胸痛在什么位置，是什么感觉？')]
    dev += [dict(id=i,case_id=c,question=q,expected_route='answer') for i,c,q in variants]
    rows=[];policies=[];neutral={}
    for item in dev:
        case=load_case(item['case_id']);t=Transcript.parse(dict(request_id=item['id'],text=item['question'],source='typed',final=True))
        p=plan(case,t,())
        assert p.route==item['expected_route']
        if p.route!='answer':policies.append(dict(id=item['id'],route=p.route,question=item['question']));continue
        messages=prompt_messages(p,item['question'])
        prompt=env.from_string(template).render(messages=messages,add_generation_prompt=True,enable_thinking=False)
        req=dict(id=item['id'],op='generate',prompt=prompt,max_tokens=24,logits_mode='final',
                 prefill_chunk=256,cache_policy='R0',state_fingerprint=False,profile=False,
                 application=dict(case_id=item['case_id'],question=item['question'],case_sha256=case.sha256,
                                  required_fact_ids=list(p.required_fact_ids),plan=p.to_dict(),messages=messages))
        rows.append(req)
        # Prefix ends before the JSON quoted dynamic question; never assume 71 is neutral.
        neutral[item['id']]=prompt[:prompt.index(json.dumps(item['question'],ensure_ascii=False))]
    assert len(rows)==25 and len(policies)==7
    binary=Path('/home/member-a/kv260-build/a12-cpu01-integrated-20261024-v1/pc/qwen35-a12')
    build=j(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json')
    environment={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_'))}
    environment.update(LD_LIBRARY_PATH=str(Path(build['workspace'])/'pc'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
    worker=OwnedWorker([str(binary),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8'],
                       directory=OUT/'pc-tokenizer',env=environment,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+900)
    ready=worker.get(120);assert ready['type']=='ready';save(OUT/'PC_READY.json',ready)
    def tokenize(prompt,rid):
        worker.send(dict(id=rid,op='tokenize',prompt=prompt));r=worker.get(30)
        assert r['type']=='tokens' and r['id']==rid
        return r['tokens']
    for r in rows:
        r['tokens']=tokenize(r['prompt'],r['id'])
        prefix=tokenize(neutral[r['id']],r['id']+'-neutral')
        r['prefix_audit']=dict(neutral_text=neutral[r['id']],neutral_stable_tokens=lcp(prefix,r['tokens']),
                               full_tokens=len(r['tokens']),isolated_prefix_tokens=len(prefix))
    assert worker.close(15)
    frozen={r['id']:r for r in old};same=[]
    for r in rows:
        if r['id'] in frozen:
            assert r['prompt']==frozen[r['id']]['prompt'] and r['tokens']==frozen[r['id']]['tokens']
            same.append(r['id'])
    assert len(same)==17
    common=min(lcp(rows[0]['tokens'],r['tokens']) for r in rows[:17])
    save(OUT/'WORKLOADS.json',dict(schema='A12_TT10_WORKLOADS_V1',real_inputs=rows,policy_inputs=policies,
         old_development_17_byte_and_token_equal=same,teacher_probes=[dict(id='suffix_'+str(n),tokens=list(range(1,n+1)),teacher_tokens=[10],max_tokens=1,
            scope='FUTURE_SUFFIX_LENGTH_PROXY_NOT_CACHE_HIT') for n in (1,8,9,16,17,24,32,48)],
         future_context_boundaries=[0,1,8,9,128,1022,1024],performance_frozen_before_BOARD=True))
    audit=[]
    for r in rows:
        p=r['prefix_audit'];k=p['neutral_stable_tokens'];audit.append(dict(id=r['id'],case_id=r['application']['case_id'],
            full_tokens=len(r['tokens']),neutral_stable_prefix=k,new_after_neutral=len(r['tokens'])-k,
            new_after_dev_common=len(r['tokens'])-common if r['id'] in frozen else None,
            supported_short_input=len(r['tokens'])<=128,actual_cache_hit=False))
    save(OUT/'TOKEN_PREFIX_AUDIT.json',dict(domain='PC_REAL_NATIVE_TOKENIZER',original_17_common_prefix=common,
         neutral_prefix_is_not_71=True,rows=audit,cache_restore='NOT_IMPLEMENTED',BOARD='NOT_TESTED'))
    sources=[template_path,ROOT/'eval/qwen35/a02/dev/questions-v2.json',ROOT/'models/model.lock.json',ROOT/'platform/toolchain.lock.json']
    sources+=list((ROOT/'system_qwen35/app').glob('*.py'))+list((ROOT/'system_qwen35/cases').glob('*.json'))
    sources+=list((ROOT/'platform/qwen35/a12').glob('tt10_00*.py'))
    save(OUT/'SOURCE_PINS.json',{p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sources})
    for rel in ['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DECISIONS.md','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md']:
        p=OUT/'before'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p)
    print(json.dumps(dict(status='INPUTS_FROZEN_PC_TOKENIZER_PASS',real_inputs=len(rows),policy_inputs=len(policies),old_17_unchanged=len(same),common=common,
                         neutral_prefix=sorted({x['neutral_stable_prefix'] for x in audit}),new_range=[min(x['new_after_neutral'] for x in audit),max(x['new_after_neutral'] for x in audit)])))

if __name__=='__main__':main()
