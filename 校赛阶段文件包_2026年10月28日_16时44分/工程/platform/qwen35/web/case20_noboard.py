"""Receive no devices: audit, generate and benchmark the twenty-case CPU candidate."""
import argparse
import copy
from dataclasses import replace
import gc
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DATA=ROOT/'data/patient_cases/chest_pain_20_20261027_v1'
PARENT=ROOT/'release/a12_realtime_tail_20261027_1446_BJT_v2/dual-neutral34-43-t4-out32'
sys.path.insert(0,str(HERE/'vendor/web_gateway/src'))
from answer_cache_build import enumerate_plans
from verified_answer_cache import SCHEMA,VerifiedAnswerCache,model_identity,key_data,digest,file_sha
from natural_patient_prompt import prompt_messages,policy_sha256,POLICY

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def stats(xs):return dict(min=min(xs),median=statistics.median(xs),max=max(xs),samples=len(xs))

def audit(out):
    from patient_web.reference.domain import CASE_IDS,load_case,Transcript
    from patient_web.reference.planning import plan
    from patient_web.reference.checking import check
    questions=read(DATA/'question_set.json')['entries'];mismatch=[]
    for q in questions:
        p=plan(load_case(q['case_id']),Transcript('audit',q['question'],None,'typed',None,None),())
        if p.route!='answer' or set(p.required_fact_ids)!=set(q['expected_fact_ids']):mismatch.append(q)
    plans={(c.case_id,p.required_fact_ids):p for c,p in enumerate_plans()}
    bad=[]
    for r in read(DATA/'answer_candidates.json')['entries']:
        p=plans[r['case_id'],tuple(r['required_fact_ids'])]
        if check(p,r['text'])['status']!='pass':bad.append(r['candidate_id'])
    natural_bad=[(c.case_id,p.required_fact_ids) for c,p in enumerate_plans()
                 if check(p,prompt_messages(p,'')[-1]['content'].split('\n',1)[1])['status']!='pass']
    original_equal={cid:file_sha(DATA/'cases'/f'{cid}.json')==file_sha(ROOT/'system_qwen35/cases'/f'{cid}.json') for cid in CASE_IDS[:3]}
    report=dict(status='PASS' if not(mismatch or bad or natural_bad) and all(original_equal.values()) else 'FAIL',
        cases=len(CASE_IDS),plans=len(plans),questions=len(questions),routing_mismatches=mismatch,
        authored_candidate_failures=bad,natural_surface_failures=natural_bad,original_byte_equal=original_equal,
        BOARD='NOT_TESTED',board_actions=0)
    save(out/'AUDIT.json',report);return report

def generate(a):
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    from patient_web.reference.checking import check
    deps=read(PARENT/'PC_DEPENDENCIES.json')
    sys.path.insert(0,str(PARENT/'continuous/bundle/platform/qwen35/a12'))
    from supervisor import OwnedWorker
    from realtime_draft import STRATEGY,fact_copy_draft
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);(out/'proof').mkdir()
    template=ImmutableSandboxedEnvironment().from_string((PARENT/'continuous/bundle/control/chat_template.jinja').read_text(encoding='utf-8'))
    all_plans=list(enumerate_plans())
    plans=all_plans
    if a.pilot:
        plans=[next((c,p) for c,p in all_plans if c.case_id==f'SYN_CP_{i:02}' and p.required_fact_ids==(slot,))
               for i,slot in enumerate(('location','quality','trigger','allergy','duration','dyspnea','onset','relief','severity','medications',
                                        'radiation','medications','allergy','medications','quality','severity','medications','relief','medications','location'),1)]
        plans+=sorted((x for x in all_plans if len(x[1].facts)==2),
            key=lambda x:len(prompt_messages(x[1],'')[-1]['content']),reverse=True)[:4]
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=deps['library_dir'],OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1')
    def launch(folder,environment):
        worker=OwnedWorker([deps['binary'],deps['model'],'4','1024','all','TILED','4','8'],directory=folder,
            env=environment,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+14400,real=False)
        ready=worker.get(120)
        if ready.get('execution_kind')!='CPU_REFERENCE':raise RuntimeError('CPU worker required')
        save(folder/'ready.json',ready);return worker,ready
    def request(worker,req):
        worker.send(req)
        while True:
            r=worker.get(180)
            if r.get('id')!=req['id']:raise RuntimeError('request/result mismatch')
            if r['type']!='token':return r
    # Tokenize only public instructions; one shared snapshot for all twenty cases.
    probe,_=launch(out/'tokenizer',env)
    messages=prompt_messages(plans[0][1],'')
    full=template.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
    neutral=full.split('事实句：\n',1)[0]+'事实句：\n'
    try:tokens=request(probe,dict(op='tokenize',id='natural-neutral',prompt=neutral))['tokens']
    finally:probe.close(15)
    cfg=read(PARENT/'PC_PREFIX_CONFIG.json')
    cfg['allowed_prefixes']=[tokens]
    cfg['identity'].update(prompt_policy_sha256=policy_sha256(),natural_patient_policy_sha256=policy_sha256(),
        neutral_prefix_choices_sha256=digest([tokens]))
    cfg['identity'].pop('neutral_prefix_routing_sha256',None)
    save(out/'prefix-config-PC.json',cfg)
    profile=read(PARENT/'continuous/profile.json')
    profile.update(profile_id='natural20-t4-out32',prompt_policy=POLICY,natural_patient_policy=POLICY,
        prefix_tokens=len(tokens),prefix_token_ids=tokens,prefix_sha256=digest(tokens),cache_id='natural-t4',
        neutral_text=neutral,output_tokens=32,realtime_draft_strategy=STRATEGY,additional_neutral_prefixes=[])
    profile.pop('live_miss_prompt_policy',None)
    profile['prefix_identity'].update(prompt_policy_sha256=policy_sha256(),natural_patient_policy_sha256=policy_sha256(),
        neutral_prefix_choices_sha256=digest([tokens]))
    profile['prefix_identity'].pop('neutral_prefix_routing_sha256',None)
    save(out/'profile.json',profile)
    identity=model_identity(profile['prefix_identity'],HERE/'vendor/web_gateway/src/patient_web/reference',generation_policy=POLICY)
    env['SP_TT10_CONFIG']=str(out/'prefix-config-PC.json')
    started=time.monotonic();worker,ready=launch(out/'worker',env);entries=[];rows=[];failures=[]
    save(out/'ready.json',ready)
    try:
        warm=request(worker,dict(op='cache_create',id='warm-natural',tokens=tokens,max_tokens=1,
            confirmed_prefix=True,cache_id='natural-t4',cache_policy='R0',prefill_chunk=256,logits_mode='final',
            cache_binding_sha256=ready['prefix_cache']['binding_sha256']))
        save(out/'warm.json',warm)
        for i,(case,p) in enumerate(plans,1):
            rid=f'natural-{i:04}';messages=prompt_messages(p,'')
            prompt=template.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
            req=dict(id=rid,prompt=prompt,max_tokens=32,cache_policy='TT10_REQUIRE_HIT',cache_id='natural-t4',
                cache_binding_sha256=ready['prefix_cache']['binding_sha256'],prefill_chunk=256,logits_mode='final',
                profile=False,diagnostic_report=False)
            if not a.serial:req.update(draft_strategy=STRATEGY,draft_text=fact_copy_draft(messages))
            begin=time.monotonic();r=request(worker,req);elapsed=(time.monotonic()-begin)*1000
            save(out/'proof'/f'{rid}.json',r)
            checked=check(p,r.get('text'));ok=r.get('status')=='OK' and r.get('eos') is True and checked['status']=='pass'
            row=dict(id=rid,case_id=case.case_id,slots=list(p.required_fact_ids),text=r.get('text'),
                accepted=ok,checker=checked,eos=r.get('eos'),output_tokens=len(r.get('output_tokens',[])),
                wall_ms=elapsed,draft_accepted=r.get('speculative_decoding',{}).get('accepted'),
                reused_tokens=r.get('prefix_cache_request',{}).get('reused_tokens'))
            rows.append(row)
            if ok:
                text=r['text'];kd=key_data(case,p,identity);text_sha=hashlib.sha256(text.encode()).hexdigest()
                entries.append(dict(key=digest(kd),key_data=kd,text=text,text_sha256=text_sha,origin=dict(status='OK',eos=True,
                    teacher_forced=False,execution_kind='CPU_REFERENCE',native_request_id=rid,result_path=f'proof/{rid}.json',
                    result_sha256=file_sha(out/'proof'/f'{rid}.json'),text_sha256=text_sha,binary_sha256=file_sha(deps['binary']),
                    prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),output_tokens=len(r['output_tokens']))))
            else:failures.append(row)
            if i%25==0 or not ok or a.pilot:
                print(json.dumps(dict(completed=i,total=len(plans),failures=len(failures),latest=row if not ok or a.pilot else None),ensure_ascii=False),flush=True)
            if a.limit and i>=a.limit:break
        closed=worker.close(15)
        doc=dict(schema=SCHEMA,identity=identity,authorization_included=False,entries=entries)
        # Identity lives once at catalog level; each key binds its SHA instead of repeating it.
        (out/'catalog.json').write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
        gc.collect();tracemalloc.start()
        cache=VerifiedAnswerCache(out/'catalog.json',identity=identity,expected_sha256=file_sha(out/'catalog.json'))
        retained,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        report=dict(status='PASS' if not failures and len(rows)==len(plans) and closed else 'INCOMPLETE',
            expected=len(plans),accepted=len(entries),model_calls=len(rows),failures=failures,rows=rows,
            worker_exit=worker.process.returncode,elapsed_s=time.monotonic()-started,
            catalog_bytes=(out/'catalog.json').stat().st_size,catalog_sha256=file_sha(out/'catalog.json'),
            cache_python_retained_bytes=retained,cache_python_peak_bytes=peak,prefix_tokens=len(tokens),
            prefix_retained_bytes=warm.get('prefix_cache',{}).get('retained_bytes'),
            latency_ms=stats([r['wall_ms'] for r in rows]),max_output_tokens=max(r['output_tokens'] for r in rows),
            draft_accepts=sum(r['draft_accepted'] is True for r in rows),BOARD='NOT_TESTED',board_actions=0)
        save(out/'RESULT.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('rows','failures')},ensure_ascii=False),flush=True)
        return report
    finally:
        if not worker.closed:worker.close(15)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('audit','generate'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--pilot',action='store_true');p.add_argument('--serial',action='store_true')
    p.add_argument('--limit',type=int);a=p.parse_args()
    if a.action=='audit':a.output.mkdir(parents=True,exist_ok=True);print(json.dumps(audit(a.output),ensure_ascii=False))
    else:generate(a)
