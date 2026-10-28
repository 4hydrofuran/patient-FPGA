"""Small real-model matrix for severity latency: existing threads/chunks/prefix slots."""
import argparse
import copy
import itertools
import json
import os
from pathlib import Path
import statistics
import sys
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'vendor/web_gateway/src'));sys.path.insert(0,str(ROOT/'platform/qwen35/a12'))
from supervisor import OwnedWorker
from compact_fact_prompt import prompt_messages
from realtime_draft import fact_copy_draft,STRATEGY
from answer_cache_build import enumerate_plans
from patient_web.reference.checking import check
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def run(a):
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    parent=ROOT/'release/a12_realtime_model_draft_20261027_v1/realtime34-threads3-out32'
    deps=read(parent/'PC_DEPENDENCIES.json');base=read(a.prefix_source/'prefix-config-PC.json');extra=read(a.prefix_source/'EXTRA_PREFIX.json')
    template=ImmutableSandboxedEnvironment().from_string((parent/'continuous/bundle/control/chat_template.jinja').read_text(encoding='utf-8'))
    cases=[(i,c,p) for i,(c,p) in enumerate(enumerate_plans(),1) if p.required_fact_ids==('severity',)]
    rows=[]
    for threads in (3,4):
        folder=out/('threads'+str(threads));folder.mkdir();(folder/'proof').mkdir()
        config=copy.deepcopy(base);config['identity']['threads']=config['identity']['kernel_threads']=threads
        save(folder/'prefix-config.json',config)
        env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
        env.update(LD_LIBRARY_PATH=deps['library_dir'],OMP_NUM_THREADS=str(threads),OPENBLAS_NUM_THREADS='1',SP_TT10_CONFIG=str(folder/'prefix-config.json'))
        worker=OwnedWorker([deps['binary'],deps['model'],str(threads),'1024','all','TILED',str(threads),'8'],
            directory=folder/'worker',env=env,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+7200,real=False)
        try:
            ready=worker.get(120);assert ready['type']=='ready' and ready['execution_kind']=='CPU_REFERENCE';save(folder/'ready.json',ready)
            binding=ready['prefix_cache']['binding_sha256']
            def raw(req):
                worker.send(req)
                while True:
                    r=worker.get(180);assert r.get('id')==req['id']
                    if r['type']!='token':break
                save(folder/'proof'/(req['id']+'.json'),dict(request=req,result=r))
                assert r['type'] in ('result','cache_created') and r['status']=='OK' and r['state_cleared_before_response'] and r['state_position_after_clear']==-1
                return r
            for n,tokens in enumerate(config['allowed_prefixes']):
                raw(dict(id='warm'+str(n),op='cache_create',tokens=tokens,cache_id='prefix'+str(n),max_tokens=1,
                    confirmed_prefix=True,cache_binding_sha256=binding,cache_policy='R0',prefill_chunk=256,logits_mode='final'))
            settings=list(itertools.product((256,8),(0,1),range(a.repeats)))
            # Interleave prefix/chunk settings rather than comparing only long contiguous blocks.
            settings.sort(key=lambda x:(x[2],x[0],x[1]))
            index=0
            for chunk,slot,repeat in settings:
                for old_index,case,plan in cases:
                    index+=1;messages=prompt_messages(plan,'')
                    prompt=template.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
                    r=raw(dict(id='matrix-'+str(index),prompt=prompt,max_tokens=32,cache_id='prefix'+str(slot),cache_binding_sha256=binding,
                        cache_policy='TT10_REQUIRE_HIT',prefill_chunk=chunk,logits_mode='final',profile=False,diagnostic_report=False,
                        draft_strategy=STRATEGY,draft_text=fact_copy_draft(messages)))
                    reference=read(ROOT/'evidence/model_pl_A/20261027-realtime-miss-opt-v1/pairs198-final/proof'/f'pair-{old_index:03d}-serial.json')['result']
                    assert r['eos'] and not r['teacher_forced'] and check(plan,r['text'])['status']=='pass'
                    assert r['output_tokens']==reference['output_tokens'] and r['text']==reference['text']
                    assert r['speculative_decoding']['accepted']
                    rows.append(dict(threads=threads,chunk=chunk,prefix_tokens=len(config['allowed_prefixes'][slot]),case_id=case.case_id,repeat=repeat,
                        native_ms=r['request_profile']['native_request_wall_ms'],prefill_ms=r['prefill_ms'],restore_ms=r['prefix_cache_request']['restore_ms'],
                        cpu_runs=r['request_profile']['cpu_counters']['run_count_delta']))
                    save(out/'PROGRESS.json',dict(completed=len(rows),last=rows[-1]))
            assert worker.close(15)
        finally:
            if not worker.closed:worker.close(15)
    summaries=[]
    for threads,chunk,prefix in itertools.product((3,4),(256,8),(34,37)):
        times=[r['native_ms'] for r in rows if (r['threads'],r['chunk'],r['prefix_tokens'])==(threads,chunk,prefix)]
        summaries.append(dict(threads=threads,chunk=chunk,prefix_tokens=prefix,min=min(times),median=statistics.median(times),max=max(times),samples=len(times)))
    result=dict(status='PASS_REAL_TARGET_SETTING_MATRIX',rows=rows,summaries=summaries,total=len(rows),answer_cache_reads=0,BOARD='NOT_TESTED')
    save(out/'RESULT.json',result);print(json.dumps(summaries,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prefix-source',type=Path,default=ROOT/'evidence/model_pl_A/20261027-realtime-tail-opt-v2/prefix-repeat')
    p.add_argument('--repeats',type=int,default=2)
    run(p.parse_args())
