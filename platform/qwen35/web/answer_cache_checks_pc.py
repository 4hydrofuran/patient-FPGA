"""One actual CPU miss plus cache/policy/session regressions through the real web factory."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
from answer_cache_paths import vendor_source,default_parent,project_root
from verified_answer_cache import VerifiedAnswerCache,model_identity,file_sha

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def verify(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);parent=a.parent.resolve();window=parent/'continuous'
    for p in (window/'bundle/platform/qwen35/a12',vendor_source()):sys.path.insert(0,str(p))
    from fastapi.testclient import TestClient
    from supervisor import OwnedWorker
    from board_case import load_native
    from interactive_case import CachedTransport
    from continuous_sessions import install
    from short_prompt_adapter import prompt_messages
    from patient_web.reference.domain import load_case,Transcript
    from patient_web.reference.planning import plan
    from verified_answer_cache import key_data,digest
    src=HERE/'web_managed.py' if (HERE/'web_managed.py').is_file() else project_root(parent)/'system_qwen35/app/web_managed.py'
    s=importlib.util.spec_from_file_location('cache_checks_web',src);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    deps=read(parent/'PC_DEPENDENCIES.json');profile=read(window/'profile.json')
    identity=model_identity(profile['prefix_identity'],vendor_source()/'patient_web/reference')
    data=read(a.catalog);case=load_case('SYN_CP_01')
    p=plan(case,Transcript.parse(dict(request_id='miss',text='疼痛在哪里？',source='typed',final=True)),())
    missing=digest(key_data(case,p,identity));data['entries']=[r for r in data['entries'] if r['key']!=missing]
    if len(data['entries'])!=197:raise RuntimeError('test catalog must remove exactly one real entry')
    save(out/'partial-catalog.json',data)
    cache=VerifiedAnswerCache(out/'partial-catalog.json',identity=identity,expected_sha256=file_sha(out/'partial-catalog.json'))
    cfg_path=project_root(parent)/'evidence/model_pl_A/20261027-fast-response-v1/release-model/prefix-config-PC.json'
    cfg=read(cfg_path);p=copy.deepcopy(profile);p['prefix_identity']=cfg['identity']
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=deps['library_dir'],SP_TT10_CONFIG=str(cfg_path),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
    worker=OwnedWorker([deps['binary'],deps['model'],'2','1024','all','TILED','2','8'],directory=out/'worker',env=env,
        health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+1800,real=False)
    try:
        ready=worker.get(120)
        api=type('PC',(),{'receive':staticmethod(lambda w,*args,**kw:w.get(kw.get('timeout',180)))})()
        transport=CachedTransport(worker,None,out,api,profile=p,maximum_questions=None)
        transport.warm(ready,read(window/'bundle/control/requests.json')[1])
        native=load_native(window,project_root(parent))(transport,ready,max_output_tokens=24,domain='PC_REFERENCE',
            template_path=window/'bundle/control/chat_template.jinja')
        app=m.create_app(native,is_ready=lambda:not native.broken,remaining_seconds=lambda:999,
            prompt_builder=prompt_messages,answer_cache=cache,domain='PC')
        c=app.state.coordinator;install(c,out/'consultations')
        def wait():
            end=time.monotonic()+180
            while c.work is not None and time.monotonic()<end:time.sleep(.005)
            if c.work is not None:raise TimeoutError('real web turn not completed')
        with TestClient(app) as client:
            if not c.initialized.wait(5):raise RuntimeError('web start failed')
            sid=c.create_session('start',case.case_id)['session_id'];url='/ui/v1/sessions/'+sid
            responses=[]
            for rid,text,expected in [('miss','疼痛在哪里？','MODEL'),('hit','每次疼痛持续多久？','MODEL_CACHE')]:
                if client.post(url+'/turns',json=dict(request_id=rid,text=text)).status_code!=202:raise RuntimeError('submit failed')
                wait();turn=client.get(url+'/turns/'+rid).json();response=c.conversations[sid].business._received[rid]['response']
                if turn.get('status')!='COMPLETED' or turn.get('answer_source')!=expected:raise RuntimeError('wrong hit/miss source')
                if response['final_check']['status']!='pass':raise RuntimeError('check failed')
                if expected=='MODEL' and (not response['model_result']['eos'] or response['model_result']['actual_backend']!='CPU_REFERENCE'):
                    raise RuntimeError('miss was not actual checked CPU generation')
                dup=client.post(url+'/turns',json=dict(request_id=rid,text=text)).json()
                if not dup.get('replayed'):raise RuntimeError('duplicate not idempotent')
                responses.append(dict(turn=turn,response=response))
            if native.count!=1:raise RuntimeError('miss/hit did not produce exactly one actual model request')
            c.finish(sid,'finish')
            if c.evaluation(sid)['rule_score']['score']!=20:raise RuntimeError('score not frozen at20')
            save(out/'HIT_MISS.json',responses)
            original={r['id']:r for r in read(project_root(parent)/'eval/qwen35/a02/dev/questions-v2.json')}
            policies=[]
            for row in read(parent/'COHORT.json')['policy_inputs']:
                before=native.count;hits=cache.hits
                psid=c.create_session('policy-'+row['id'],original[row['id']]['case_id'])['session_id']
                c.submit(psid,row['id'],row['question']);wait()
                response=c.conversations[psid].business._received[row['id']]['response']
                if native.count!=before or cache.hits!=hits or response['llm_calls']!=0 or response['answer_plan']['route']!=row['route']:
                    raise RuntimeError('policy consulted model/cache or changed route')
                policies.append(dict(id=row['id'],model_calls=0,route=row['route']));c.finish(psid,'finish-'+row['id'])
            # Finish/new-case beyond eight sessions exercises archived v2 turn receipts.
            saved=[]
            for i in range(10):
                nsid=c.create_session('archive-'+str(i),'SYN_CP_03')['session_id']
                c.submit(nsid,'duration-'+str(i),'每次疼痛持续多久？');wait();c.finish(nsid,'end-'+str(i));saved.append(nsid)
            archived=c.snapshot(saved[0]);archived_turn=c.turn_result(saved[0],'duration-0')
            if len(c.conversations)!=8 or archived_turn['answer_source']!='MODEL_CACHE' or not archived['closed']:
                raise RuntimeError('archived cache session not readable')
            if native.count!=1:raise RuntimeError('cached new cases called model')
        if worker.closed:raise RuntimeError('web shutdown closed owned worker')
        if not worker.close(15):raise RuntimeError('actual CPU worker not closed normally')
        result=dict(status='PASS_ACTUAL_CPU_MISS_CACHE_POLICY_LIFECYCLE',actual_model_calls=1,
            policy_items=policies,same_session_score=20,archived_cache_sessions=10,retained_in_memory=8,
            worker_exit=worker.process.returncode,cache=cache.report(),original_Owner_hardware_restore='NOT_TESTED',BOARD='NOT_TESTED')
        save(out/'RESULT.json',result);return result
    finally:
        if not worker.closed:worker.close(15)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--parent',type=Path,default=default_parent());p.add_argument('--output',type=Path,required=True)
    print(json.dumps(verify(p.parse_args()),indent=2))
