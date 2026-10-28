"""Actual x86 CPU generation through the derived managed web/Session path."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def verify_model(args):
    root=Path(args.bundle).resolve();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    dependencies=read(root/'PC_DEPENDENCIES.json')
    project=Path(dependencies['project_root'])
    binary=args.pc_binary or Path(dependencies['binary'])
    lib=args.pc_library_dir or Path(dependencies['library_dir'])
    model=args.model or Path(dependencies['model'])
    window=root/'continuous';bundle=window/'bundle'
    for p in (bundle/'platform/qwen35/a12',window/'web_gateway/src',window):sys.path.insert(0,str(p))
    # Resolve web dependencies before the first model process, with no downloads.
    from fastapi.testclient import TestClient
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    from patient_web.reference.domain import load_case,Transcript,digest as case_digest
    from patient_web.reference.planning import plan
    from patient_web.reference.checking import prompt_messages as legacy_prompt
    from patient_web.reference.session import Session
    from web_managed import create_app
    from board_case import load_native,WorkerTransport
    from continuous_sessions import install
    from interactive_case import CachedTransport
    from fast_response_profile import load_profile,builder,digest
    from resource_probe_policy import ordinary_comparison
    from supervisor import OwnedWorker
    profile=load_profile(window/'profile.json')
    if profile['prompt_policy']!='facts-only-02':raise ValueError('25-case model suite requires the short profile')
    cohort=read(root/'COHORT.json');rows=cohort['real_inputs']
    template_path=bundle/'control/chat_template.jinja'
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=str(lib),OMP_NUM_THREADS=str(profile['threads']),OPENBLAS_NUM_THREADS='1')
    workers=[];model_results=[];policies=[];comparisons=[]
    def launch(name,environment):
        w=OwnedWorker([str(binary),str(model),str(profile['threads']),'1024','all','TILED',str(profile['kernel_threads']),'8'],
            directory=out/name,env=environment,health=lambda:None,max_runs=1,max_loads=1,
            expires=time.monotonic()+1800,real=False)
        workers.append(w);ready=w.get(120)
        if ready.get('type')!='ready' or ready.get('execution_kind')!='CPU_REFERENCE':raise RuntimeError('actual CPU ready differs')
        save(out/(name+'-ready.json'),ready)
        return w,ready
    def terminal(w,request,expected):
        w.send(request)
        while True:
            r=w.get(180)
            if r.get('id')!=request['id']:raise RuntimeError('foreign CPU response')
            if r['type']!='token':break
        if r['type']!=expected:raise RuntimeError('unexpected CPU terminal: '+str(r))
        return r
    started=time.monotonic()
    try:
        tokenizer,_=launch('tokenizer',env)
        libraries={}
        for line in (Path('/proc')/str(tokenizer.process.pid)/'maps').read_text().splitlines():
            path=Path(line.split()[-1])
            if not path.is_absolute():continue
            name=path.name.split('.so.')[0]+'.so' if '.so.' in path.name else path.name
            if name.startswith(('libllama.','libggml','libsp_linear')):libraries[name]=sha(path)
        compiled=ImmutableSandboxedEnvironment().from_string(template_path.read_text(encoding='utf-8'))
        prompt_builder=builder(profile)
        token_rows=[]
        for row in rows:
            item=row['application'];case=load_case(item['case_id'])
            transcript=Transcript.parse(dict(request_id=row['id'],text=item['question'],source='typed',final=True))
            p=plan(case,transcript,())
            if case.sha256!=item['case_sha256'] or digest(p.to_dict())!=digest(item['plan']):raise RuntimeError('original planner/facts drift')
            messages=prompt_builder(p,item['question'])
            if messages!=item['messages']:raise RuntimeError('candidate message drift')
            rendered=compiled.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
            if rendered!=row['prompt']:raise RuntimeError('candidate template drift')
            tokens=terminal(tokenizer,dict(id='tokenize-'+row['id'],op='tokenize',prompt=rendered),'tokens')['tokens']
            if tokens!=row['tokens'] or tokens[:profile['prefix_tokens']]!=profile['prefix_token_ids']:
                raise RuntimeError('actual token prefix/full boundary differs')
            token_rows.append(dict(id=row['id'],full_tokens=len(tokens),reused_tokens=profile['prefix_tokens'],new_tokens=len(tokens)-profile['prefix_tokens']))
        neutral=terminal(tokenizer,dict(id='tokenize-neutral',op='tokenize',prompt=profile['neutral_text']),'tokens')['tokens']
        if neutral!=profile['prefix_token_ids']:raise RuntimeError('neutral/full token boundary differs')
        if not tokenizer.close(15):raise RuntimeError('tokenizer close failed')
        save(out/'TOKEN_BOUNDARIES.json',token_rows)
        pc_config=read(bundle/'control/prefix-config.json')
        pc_config['identity'].update(executable_sha256=sha(binary),libraries=libraries)
        save(out/'prefix-config-PC.json',pc_config)
        pc_profile=copy.deepcopy(profile);pc_profile['prefix_identity']=pc_config['identity']
        env['SP_TT10_CONFIG']=str(out/'prefix-config-PC.json')
        worker,ready=launch('model',env)
        api=type('PCProtocol',(),{'receive':staticmethod(lambda w,*a,**kw:w.get(kw.get('timeout',180)))})()
        transport=CachedTransport(worker,None,out,api,profile=pc_profile,maximum_questions=None)
        warm=read(bundle/'control/requests.json')[1]
        transport.warm(ready,warm)
        save(out/'warm-result.json',transport.warm_result)
        native=load_native(window,project)(transport,ready,max_output_tokens=24,domain='PC_REFERENCE',template_path=template_path)
        app=create_app(native,is_ready=lambda:transport.warm_result is not None and not worker.closed,
            remaining_seconds=lambda:worker.expires-time.monotonic(),prompt_builder=prompt_builder,domain='PC')
        c=app.state.coordinator;install(c,out/'consultations')
        def question(client,row,suffix='hit',session_id=None,finish=True):
            item=row['application'];rid=row['id']+'-'+suffix
            if session_id is None:
                start=client.post('/ui/v1/sessions',json=dict(request_id='start-'+rid,case_id=item['case_id']))
                if start.status_code!=201:raise RuntimeError(start.text)
                session_id=start.json()['session_id']
            sid=session_id;url='/ui/v1/sessions/'+sid
            begin=time.monotonic_ns()
            posted=client.post(url+'/turns',json=dict(request_id=rid,text=item['question']))
            if posted.status_code!=202:raise RuntimeError(posted.text)
            deadline=time.monotonic()+180
            while True:
                with c.lock:
                    idle=c.work is None
                if idle:break
                if time.monotonic()>deadline:raise TimeoutError('CPU web completion deadline')
                time.sleep(.005)
            turn=c.turn_result(sid,rid)
            if turn['status']!='COMPLETED' or turn['answer_source']!='MODEL' or turn['actual_backend']!='CPU_REFERENCE':
                raise RuntimeError('actual CPU web turn refused: '+str(turn))
            response=c.conversations[sid].business._received[rid]['response']
            result=response['model_result']
            if not result['eos'] or response['candidate_check']['status']!='pass' or response['final_check']['status']!='pass':
                raise RuntimeError('original checker/EOS failed')
            if response['candidate']!=result['text'] or response['text']!=result['text']:raise RuntimeError('raw model text replaced')
            if list(response['answer_plan']['required_fact_ids'])!=list(item['required_fact_ids']):raise RuntimeError('request facts changed')
            # HTTP result/evaluation, original request text and publication all remain exercised.
            snapshot=client.get(url).json()
            if next(t for t in snapshot['turns'] if t['request_id']==rid)['question']!=item['question']:raise RuntimeError('original question lost')
            checked_http_ms=(time.monotonic_ns()-begin)/1e6
            evaluation=None
            if finish:
                if client.post(url+'/finish',json={'request_id':'finish-'+rid}).status_code!=200:raise RuntimeError('finish failed')
                evaluation=client.get(url+'/evaluation').json()
            save(out/(rid+'.json'),dict(turn=turn,response=response,evaluation=evaluation,
                post_to_checked_turn_ms=checked_http_ms,BOARD='NOT_TESTED'))
            return result,dict(id=rid,session_id=sid,answer_source='MODEL',eos=True,final_check='pass',
                full_tokens=result['prompt_tokens'],output_tokens=len(result['output_tokens']),
                prefix_cache=result['prefix_cache_request'],timing=turn['timing'],raw_model_text=result['text'])
        with TestClient(app) as client:
            if not c.initialized.wait(5):raise RuntimeError('web initialization failed')
            for row in rows:
                result,summary=question(client,row)
                if not result['prefix_cache_request']['hit'] or result['prefix_cache_request']['reused_tokens']!=34:
                    raise RuntimeError('short prefix not actually hit')
                model_results.append(summary)
                print('PC_WEB_MODEL '+row['id']+' MODEL EOS CHECK_PASS',flush=True)
            # Representatives: longest, unknown fact, and two facts, de-duplicated.
            representatives=list(dict.fromkeys([max(rows,key=lambda r:len(r['tokens']))['id'],'DEV-011','V08']))
            for index in representatives:
                row=next(r for r in rows if r['id']==index)
                native.worker=WorkerTransport(worker,None,out,api)
                a,_=question(client,row,'R0-pair')
                native.worker=transport
                b,_=question(client,row,'hit-pair')
                comparisons.append(dict(id=index,**ordinary_comparison(a,b)))
            # Two actual checked answers in one consultation reuse this same worker/cache.
            first_row=next(r for r in rows if r['id']=='DEV-004')
            follow_row=next(r for r in rows if r['id']=='DEV-001')
            _,first_multi=question(client,first_row,'multi-first',finish=False)
            _,second_multi=question(client,follow_row,'multi-followup',session_id=first_multi['session_id'])
            multi=c.snapshot(first_multi['session_id'])
            evaluation=c.evaluation(first_multi['session_id'])
            if len(multi['turns'])!=2 or not multi['closed'] or evaluation['rule_score']['score']!=20:
                raise RuntimeError('same-session followup/score freeze differs')
            save(out/'CONTINUOUS.json',dict(status='PASS_ACTUAL_CPU_SAME_SESSION_TWO_TURNS',
                first=first_multi,followup=second_multi,score=20,worker_pid=worker.process.pid,
                prefix_warmed_once=True,BOARD='NOT_TESTED'))
            # Policy-only inputs use real gateway sessions and must make zero calls.
            policy_cases=read(root/'POLICY_CASES.json')
            for row in cohort['policy_inputs']:
                rid=row['id'];before=native.count
                sid=c.create_session('policy-start-'+rid,policy_cases[rid])['session_id']
                c.submit(sid,rid,row['question'])
                deadline=time.monotonic()+5
                while c.work is not None and time.monotonic()<deadline:time.sleep(.005)
                if c.work is not None:raise TimeoutError('policy completion deadline')
                response=c.conversations[sid].business._received[rid]['response']
                if native.count!=before or response['llm_calls']!=0 or response['answer_plan']['route']!=row['route']:
                    raise RuntimeError('policy unexpectedly called model or route drifted')
                policies.append(dict(id=rid,route=row['route'],model_calls=0,final_check=response['final_check']))
                c.finish(sid,'policy-finish-'+rid)
        # Original app shutdown only detaches; worker remains owned by this PC scope.
        if worker.closed:raise RuntimeError('web layer closed native ownership')
        old_prefix=read(root/'LEGACY_PC.json')['prefix_tokens']
        old_binding=read(root/'LEGACY_PC.json')['binding_sha256']
        denied=terminal(worker,dict(id='old70-rejected',op='cache_create',tokens=old_prefix,max_tokens=1,
            cache_id='old70',confirmed_prefix=True,cache_binding_sha256=transport.binding),'error')
        save(out/'old-prefix-rejected.json',denied)
        if 'prefix' not in denied['message']:raise RuntimeError('old prefix rejection reason differs')
        denied=terminal(worker,dict(id='old-binding-rejected',op='generate',tokens=rows[0]['tokens'],max_tokens=1,
            cache_policy='TT10_REQUIRE_HIT',cache_id=profile['cache_id'],cache_binding_sha256=old_binding),'error')
        save(out/'old-binding-rejected.json',denied)
        if 'VERSION_BINDING_MISMATCH' not in denied['message']:raise RuntimeError('old binding not refused')
        if not worker.close(15):raise RuntimeError('actual model worker close failed')
        report=dict(status='PASS_ACTUAL_CPU_WEB_MODEL',model_items=len(model_results),policy_items=len(policies),
            representative_pairs=comparisons,model_calls=native.count,model_results=model_results,policy_results=policies,
            same_session_model_questions=2,same_session_frozen_score=20,prefix_warm_count=1,
            token_boundaries='25_ACTUAL_TOKENIZATIONS_PLUS_NEUTRAL',old70_rejected=True,old_binding_rejected=True,
            worker_exit_codes=[w.process.returncode for w in workers],elapsed_s=time.monotonic()-started,
            native_binary_sha256=sha(binary),libraries=libraries,BOARD='NOT_TESTED',board_latency_s=None,
            scope='real CPU outputs; original web planner/checker/EOS/publication/scoring; no PL/BOARD claim')
        save(out/'RESULT.json',report);return report
    except BaseException as exc:
        save(out/'FAILURE.json',dict(status='FAILED_PC_ATTEMPT',error=type(exc).__name__+': '+str(exc),
            model_items_completed=len(model_results),policies_completed=len(policies),BOARD='NOT_TESTED'))
        raise
    finally:
        for w in workers:
            if not w.closed:w.close(15)
