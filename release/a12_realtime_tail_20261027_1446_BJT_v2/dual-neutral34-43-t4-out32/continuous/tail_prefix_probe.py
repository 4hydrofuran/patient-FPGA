"""Actual model A/B: baseline neutral prefix vs two-slot generic linguistic prefixes."""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'vendor/web_gateway/src'))
sys.path.insert(0,str(ROOT/'platform/qwen35/a12'))
from fast_response_profile import digest
from compact_fact_prompt import prompt_messages,policy_sha256
from realtime_draft import fact_copy_draft,STRATEGY
from answer_cache_build import enumerate_plans
from patient_web.reference.checking import check
from supervisor import OwnedWorker


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stats(xs):return dict(min=min(xs),median=statistics.median(xs),max=max(xs),samples=len(xs))


def run(a):
    global prompt_messages,policy_sha256
    if a.severity_first:
        from severity_scale_prompt import prompt_messages,policy_sha256
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);(out/'proof').mkdir()
    deps=read(a.parent/'PC_DEPENDENCIES.json');profile=read(a.parent/'continuous/profile.json')
    config=read(a.parent/'PC_PREFIX_CONFIG.json')
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=deps['library_dir'],OMP_NUM_THREADS=str(a.threads),OPENBLAS_NUM_THREADS='1')
    config['identity']['threads']=config['identity']['kernel_threads']=a.threads
    primary_id='short34-t'+str(a.threads)
    template=ImmutableSandboxedEnvironment().from_string((a.parent/'continuous/bundle/control/chat_template.jinja').read_text(encoding='utf-8'))
    plans=list(enumerate_plans());worker=None;calls=0;rows=[]
    def launch(folder,environment):
        w=OwnedWorker([deps['binary'],deps['model'],str(a.threads),'1024','all','TILED',str(a.threads),'8'],directory=folder,env=environment,
            health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+7200,real=False)
        ready=w.get(120);assert ready['type']=='ready' and ready['execution_kind']=='CPU_REFERENCE'
        save(folder/'ready.json',ready);return w,ready
    probe,ready=launch(out/'tokenizer-probe',env)
    try:
        base_text=profile['neutral_text']
        if a.severity_first:
            from severity_scale_prompt import PUBLIC_SEVERITY_PREFIX
            extra_text=base_text+PUBLIC_SEVERITY_PREFIX
        else:extra_text=base_text+'疼痛程度是'+(' ' if a.suffix_space else '')
        def tokenize(rid,text):
            probe.send(dict(op='tokenize',id=rid,prompt=text));r=probe.get(30)
            assert r['type']=='tokens' and r['id']==rid
            return r['tokens']
        base=tokenize('base-neutral',base_text);extra=tokenize('severity-neutral',extra_text)
        assert base==profile['prefix_token_ids'] and extra[:len(base)]==base and len(extra)>len(base)
        assert len(extra)<=128
        selection=[]
        for i,(case,p) in enumerate(plans,1):
            prompt=template.render(messages=prompt_messages(p,''),add_generation_prompt=True,enable_thinking=False)
            tokens=tokenize('input-'+str(i),prompt)
            selected=prompt.startswith(extra_text)
            assert tokens[:len(base)]==base
            if selected:assert tokens[:len(extra)]==extra
            selection.append(dict(id=i,case_id=case.case_id,facts=p.required_fact_ids,selected_extra=selected,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),tokens=tokens))
    finally:assert probe.close(15)
    definition=dict(cache_id='severity'+str(len(extra))+'-t'+str(a.threads),prefix_tokens=len(extra),prefix_token_ids=extra,
        prefix_sha256=digest(extra),neutral_text=extra_text,scope='PUBLIC_LINGUISTIC_PREFIX_NO_CASE_VALUES',
        trigger='LONGEST_EXACT_RENDERED_PROMPT_PREFIX',label='severity_scale_label' if a.severity_first else 'severity_label')
    save(out/'EXTRA_PREFIX.json',definition);save(out/'TOKENIZED_SELECTION.json',selection)
    config['allowed_prefixes']=[base,extra]
    config['identity']['neutral_prefix_choices_sha256']=digest([base,extra])
    config['identity']['neutral_prefix_routing_sha256']=digest([definition])
    config['identity']['live_miss_prompt_policy_sha256']=policy_sha256()
    save(out/'prefix-config-PC.json',config)
    env['SP_TT10_CONFIG']=str(out/'prefix-config-PC.json')
    worker,ready=launch(out/'worker',env)
    binding=ready['prefix_cache']['binding_sha256'];warm=[]
    def raw(req):
        nonlocal calls
        start=time.monotonic();worker.send(req)
        while True:
            r=worker.get(180);assert r.get('id')==req['id']
            if r['type']!='token':break
        save(out/'proof'/(req['id']+'.json'),dict(request=req,result=r,wall_ms=(time.monotonic()-start)*1000))
        assert r['type'] in ('result','cache_created') and r['status']=='OK' and r['state_cleared_before_response'] and r['state_position_after_clear']==-1,r
        if r['type']=='result':calls+=1;assert r['eos'] and not r['teacher_forced']
        return r
    try:
        for cid,tokens in [(primary_id,base),(definition['cache_id'],extra)]:
            warm.append(raw(dict(op='cache_create',id='warm-'+cid,tokens=tokens,max_tokens=1,prefill_chunk=256,
                confirmed_prefix=True,cache_id=cid,cache_binding_sha256=binding,cache_policy='R0',logits_mode='final',profile=False,diagnostic_report=False)))
        assert len(warm[-1]['prefix_cache']['entries'])==2 and warm[-1]['prefix_cache']['retained_bytes']<=128*1024*1024
        workload=plans[:a.limit]+[item for _ in range(a.severity_repeats) for item in plans if item[1].required_fact_ids==('severity',)]
        for i,(case,p) in enumerate(workload,1):
            messages=prompt_messages(p,'');prompt=template.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
            chosen=definition if prompt.startswith(extra_text) else dict(cache_id=primary_id,prefix_tokens=len(base))
            common=dict(prompt=prompt,max_tokens=32,prefill_chunk=256,cache_policy='TT10_REQUIRE_HIT',cache_binding_sha256=binding,
                logits_mode='final',profile=False,diagnostic_report=False,draft_strategy=STRATEGY,draft_text=fact_copy_draft(messages))
            pair={}
            for mode in (('base','selected') if i%2 else ('selected','base')):
                cid=primary_id if mode=='base' else chosen['cache_id']
                request=dict(common,id=f'case-{i:03d}-{mode}',cache_id=cid)
                if mode=='base' and a.serial_reference:
                    request.pop('draft_strategy');request.pop('draft_text')
                pair[mode]=raw(request)
                r=pair[mode];assert check(p,r['text'])['status']=='pass'
                if mode=='selected' or not a.serial_reference:
                    assert r['speculative_decoding']['accepted'] and r['speculative_decoding']['target_eos_verified']
            x,y=pair['base'],pair['selected']
            assert x['text']==y['text'] and x['output_tokens']==y['output_tokens']
            reference_index=next(j for j,(c,q) in enumerate(plans,1) if c.case_id==case.case_id and q.required_fact_ids==p.required_fact_ids)
            reference=read(ROOT/'evidence/model_pl_A/20261027-realtime-miss-opt-v1/pairs198-final/proof'/f'pair-{reference_index:03d}-serial.json')['result']
            if not a.severity_first:assert y['text']==reference['text'] and y['output_tokens']==reference['output_tokens']
            assert y['prefix_cache_request']['reused_tokens']==chosen['prefix_tokens']
            rows.append(dict(id=i,case_id=case.case_id,facts=p.required_fact_ids,reused_tokens=chosen['prefix_tokens'],
                base_ms=x['request_profile']['native_request_wall_ms'],selected_ms=y['request_profile']['native_request_wall_ms']))
            save(out/'PROGRESS.json',dict(completed=i,expected=len(workload),last=rows[-1],actual_model_requests=calls))
        assert worker.close(15)
        eligible=[r for r in rows if r['reused_tokens']>len(base)]
        result=dict(status='PASS_REAL_MODEL_TWO_NEUTRAL_PREFIXES',at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            rows=rows,total=len(rows),actual_model_requests=calls,answer_cache_reads=0,primary_tokens=len(base),extra_tokens=len(extra),
            eligible=len(eligible),eligible_base_ms=stats([r['base_ms'] for r in eligible]),eligible_selected_ms=stats([r['selected_ms'] for r in eligible]),
            retained_prefix_bytes=warm[-1]['prefix_cache']['retained_bytes'],warm_model_passes=2,
            worker_exit=worker.process.returncode,native_binary_sha256=sha(deps['binary']),threads=a.threads,
            unchanged_v1_serial_tokens=not a.severity_first,actual_same_input_serial_reference=a.serial_reference,BOARD='NOT_TESTED')
        save(out/'RESULT.json',result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
    finally:
        if not worker.closed:worker.close(15)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--limit',type=int,default=198)
    p.add_argument('--severity-repeats',type=int,default=0)
    p.add_argument('--threads',type=int,choices=(3,4),default=3)
    p.add_argument('--suffix-space',action='store_true')
    p.add_argument('--severity-first',action='store_true')
    p.add_argument('--serial-reference',action='store_true')
    p.add_argument('--parent',type=Path,default=ROOT/'release/a12_realtime_model_draft_20261027_v1/realtime34-threads3-out32')
    run(p.parse_args())
