"""Build 198 typed fact keys using actual existing CPU Qwen generation, never BOARD."""
import argparse
import copy
from dataclasses import replace
import itertools
import json
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
from answer_cache_paths import vendor_source,default_parent
sys.path.insert(0,str(vendor_source()))
from verified_answer_cache import SCHEMA,model_identity,key_data,digest,file_sha


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def enumerate_plans():
    from patient_web.reference.domain import load_case,Transcript,SLOTS
    from patient_web.reference.planning import plan
    for cid in ('SYN_CP_01','SYN_CP_02','SYN_CP_03'):
        case=load_case(cid)
        base=plan(case,Transcript.parse(dict(request_id='catalog',text='疼痛在哪里？',source='typed',final=True)),())
        for n in (1,2):
            for slots in itertools.combinations(SLOTS,n):
                yield case,replace(base,intent_ids=slots,allowed_fact_ids=slots,required_fact_ids=slots,
                    facts=tuple(case.fact(s) for s in slots),evidence=(),played_history=(),already_disclosed=())


def build(output,parent):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    parent=Path(parent).resolve();deps=read(parent/'PC_DEPENDENCIES.json')
    sys.path.insert(0,str(parent/'ordinary/bundle/platform/qwen35/a12'))
    from supervisor import OwnedWorker
    from patient_web.reference.checking import check
    from short_prompt_adapter import prompt_messages
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    binary=Path(deps['binary']);model=Path(deps['model']);library=Path(deps['library_dir'])
    prefix=read(parent/'continuous/bundle/control/prefix-config.json')
    identity=model_identity(prefix['identity'],vendor_source()/'patient_web/reference')
    if file_sha(model)!=identity['assets']['model_sha256']:raise RuntimeError('actual GGUF differs from catalog identity')
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=str(library),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
    template=ImmutableSandboxedEnvironment().from_string((parent/'continuous/bundle/control/chat_template.jinja').read_text(encoding='utf-8'))
    worker=None;entries=[];failures=[];started=time.monotonic();proof=out/'proof';proof.mkdir()
    try:
        worker=OwnedWorker([str(binary),str(model),'2','1024','all','TILED','2','8'],directory=out/'worker',env=env,
            health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+5400,real=False)
        ready=worker.get(120)
        if ready.get('type')!='ready' or ready.get('execution_kind')!='CPU_REFERENCE':raise RuntimeError('CPU ready differs')
        save(out/'ready.json',ready)
        loaded={}
        for line in (Path('/proc')/str(worker.process.pid)/'maps').read_text().splitlines():
            p=Path(line.split()[-1])
            if p.is_absolute() and p.name.startswith(('libllama','libggml','libsp_linear')):loaded[p.name]=file_sha(p)
        for i,(case,p) in enumerate(enumerate_plans(),1):
            rid=f'catalog-{i:03d}';messages=prompt_messages(p,'')
            prompt=template.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
            req=dict(id=rid,prompt=prompt,max_tokens=64,cache_policy='R0',prefill_chunk=256,logits_mode='final',profile=False,diagnostic_report=False)
            begin=time.monotonic();worker.send(req)
            while True:
                r=worker.get(180)
                if r.get('id')!=rid:raise RuntimeError('foreign catalog result')
                if r['type']!='token':break
            raw=proof/(rid+'.json');save(raw,r)
            checked=check(p,r.get('text'))
            ok=(r.get('type')=='result' and r.get('status')=='OK' and r.get('eos') is True and r.get('teacher_forced') is False
                and r.get('state_cleared_before_response') is True and r.get('state_position_after_clear')==-1 and checked['status']=='pass'
                and r.get('bridge',{}).get('execution_kind')=='CPU_REFERENCE')
            kd=key_data(case,p,identity);text=r.get('text','')
            if ok:
                import hashlib
                text_sha=hashlib.sha256(text.encode()).hexdigest()
                entries.append(dict(key=digest(kd),key_data=kd,text=text,text_sha256=text_sha,origin=dict(
                    status='OK',eos=True,teacher_forced=False,execution_kind='CPU_REFERENCE',native_request_id=rid,
                    result_path='proof/'+raw.name,result_sha256=file_sha(raw),text_sha256=text_sha,
                    binary_sha256=file_sha(binary),libraries=loaded,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                    output_tokens=len(r['output_tokens']),generation_wall_s=time.monotonic()-begin)))
            else:failures.append(dict(id=rid,key_data=kd,result_path='proof/'+raw.name,checker=checked,eos=r.get('eos')))
            print(json.dumps(dict(id=rid,accepted=ok,completed=i,failures=len(failures))),flush=True)
        if not worker.close(15):raise RuntimeError('catalog worker close not confirmed')
        catalog=dict(schema=SCHEMA,identity=identity,authorization_included=False,entries=entries)
        save(out/'catalog.json',catalog)
        report=dict(status='PASS_198_REAL_MODEL_CATALOG' if not failures and len(entries)==198 else 'INCOMPLETE_REAL_MODEL_CATALOG',
            expected=198,accepted=len(entries),failures=failures,model_calls=198,worker_exit=worker.process.returncode,
            elapsed_s=time.monotonic()-started,catalog_bytes=(out/'catalog.json').stat().st_size,
            catalog_sha256=file_sha(out/'catalog.json'),identity=identity,BOARD='NOT_TESTED',board_actions=0)
        save(out/'RESULT.json',report);return report
    finally:
        if worker and not worker.closed:worker.close(15)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--parent',type=Path,default=default_parent())
    a=p.parse_args();print(json.dumps(build(a.output,a.parent),indent=2))
