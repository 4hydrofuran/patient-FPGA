"""Actual CPU HTTP/SSE service for controlled live/cache browser A/B; no BOARD I/O."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import threading
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
from answer_cache_paths import vendor_source,default_parent,project_root


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x,*,noncritical=False):
    p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # A Windows reader may temporarily deny rename on the shared WSL mount.
    for attempt in range(10):
        try:tmp.replace(p);return True
        except PermissionError:
            if attempt==9:
                if noncritical:return False
                raise
            time.sleep(.01)


def serve(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    parent=a.parent.resolve();window=parent/'continuous';deps=read(parent/'PC_DEPENDENCIES.json')
    sys.path.insert(0,str(window/'bundle/platform/qwen35/a12'))
    vendor=vendor_source() if a.mode!='live' else window/'web_gateway/src'
    sys.path.insert(0,str(vendor))
    # Cache mode consumes current sources; live mode consumes frozen v2 sources.
    if a.mode=='live':sys.path.insert(0,str(window))
    from fastapi import FastAPI
    import uvicorn
    from supervisor import OwnedWorker
    from board_case import load_native
    from interactive_case import CachedTransport
    from fast_response_profile import load_profile
    from continuous_sessions import install
    if a.mode=='live':
        from web_managed import create_app
    else:
        import importlib.util
        source=HERE/'web_managed.py' if (HERE/'web_managed.py').is_file() else project_root(parent)/'system_qwen35/app/web_managed.py'
        spec=importlib.util.spec_from_file_location('cache_pc_web_managed',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);create_app=module.create_app
    from short_prompt_adapter import prompt_messages
    if a.compact or (a.mode!='live' and read(window/'profile.json').get('live_miss_prompt_policy')):
        from compact_fact_prompt import prompt_messages
    cache=None
    if a.mode=='cache':
        from verified_answer_cache import VerifiedAnswerCache,model_identity,file_sha
        profile=load_profile(window/'profile.json')
        identity=model_identity(profile['prefix_identity'],vendor/'patient_web/reference')
        cache=VerifiedAnswerCache(a.catalog,identity=identity,expected_sha256=file_sha(a.catalog))
    profile=load_profile(window/'profile.json')
    pc_config=a.pc_prefix_config or (parent/'PC_PREFIX_CONFIG.json' if (parent/'PC_PREFIX_CONFIG.json').is_file()
        else project_root(parent)/'evidence/model_pl_A/20261027-fast-response-v1/release-model/prefix-config-PC.json')
    cfg=read(pc_config)
    threads=cfg['identity']['threads']
    if threads not in (2,3) or cfg['identity']['kernel_threads']!=threads:raise RuntimeError('PC thread identity differs')
    # Validate actual CPU executable/libs in native PrefixStore at launch.
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=deps['library_dir'],SP_TT10_CONFIG=str(pc_config.resolve()),OMP_NUM_THREADS=str(threads),OPENBLAS_NUM_THREADS='1')
    worker=None;server=None;thread=None;native=None;ready_start=time.monotonic()
    try:
        worker=OwnedWorker([str(a.binary or deps['binary']),deps['model'],str(threads),'1024','all','TILED',str(threads),'8'],
            directory=out/'worker',env=env,health=lambda:None,max_runs=1,max_loads=1,
            expires=time.monotonic()+7200,real=False)
        ready=worker.get(120)
        if ready.get('type')!='ready' or ready.get('execution_kind')!='CPU_REFERENCE':raise RuntimeError('wrong CPU ready')
        save(out/'ready.json',ready)
        p=copy.deepcopy(profile);p['prefix_identity']=cfg['identity'];p['threads']=p['kernel_threads']=threads
        p['cache_id']='short34-t'+str(threads)
        output_tokens=a.output_tokens or (32 if a.mode=='realtime' or a.realtime_draft else p['output_tokens'])
        p['output_tokens']=output_tokens
        api=type('PC',(),{'receive':staticmethod(lambda w,*args,**kw:w.get(kw.get('timeout',180)))})()
        transport=CachedTransport(worker,None,out,api,profile=p,maximum_questions=None)
        warm=copy.deepcopy(read(window/'bundle/control/requests.json')[1]);warm['cache_id']=p['cache_id']
        transport.warm(ready,warm)
        native_options=dict(max_output_tokens=output_tokens,domain='PC_REFERENCE',template_path=window/'bundle/control/chat_template.jinja')
        native_source=window
        if a.mode=='realtime' or a.realtime_draft:
            from realtime_draft import STRATEGY
            native_options['generation_strategy']=STRATEGY
            native_source=HERE if (HERE/'native_pl.py').is_file() else project_root(parent)/'system_qwen35/app'
        native=load_native(native_source,Path(deps['project_root']))(transport,ready,**native_options)
        options=dict(is_ready=lambda:not worker.closed and not native.broken,
            remaining_seconds=lambda:worker.expires-time.monotonic(),prompt_builder=prompt_messages,domain='PC')
        if cache is not None:options['answer_cache']=cache
        app=create_app(native,**options);coordinator=app.state.coordinator
        install(coordinator,out/'consultations')
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=a.port,log_level='warning'))
        thread=threading.Thread(target=server.run,daemon=True);thread.start()
        for _ in range(100):
            if server.started and coordinator.initialized.is_set():break
            time.sleep(.1)
        else:raise RuntimeError('real HTTP server not ready')
        save(out/'HTTP_READY.json',dict(status='READY',mode=a.mode,url=f'http://127.0.0.1:{a.port}/',
            startup_ready_s=time.monotonic()-ready_start,native_count=native.count,
            cache=cache.report() if cache else None,generation_strategy=getattr(native,'generation_strategy',None),threads=threads,BOARD='NOT_TESTED'))
        while not (out/'stop-request.json').exists() and time.monotonic()<worker.expires-180:
            save(out/'metrics.json',dict(mode=a.mode,native_count=native.count,worker_closed=worker.closed,
                cache=cache.report() if cache else None,coordinator_busy=coordinator.work is not None),noncritical=True)
            time.sleep(.2)
        # Original coordinator lifespan drains; its engine only detaches from ownership.
        server.should_exit=True;thread.join(timeout=180)
        if thread.is_alive():raise RuntimeError('HTTP call has not drained')
        if worker.closed:raise RuntimeError('HTTP layer closed the owned worker')
        if not worker.close(15):raise RuntimeError('normal CPU worker close not confirmed')
        save(out/'RESULT.json',dict(status='PASS_NORMAL_PC_HTTP_CLOSE',mode=a.mode,native_count=native.count,
            cache=cache.report() if cache else None,worker_exit=worker.process.returncode,
            HTTP_layer_retained_worker=True,BOARD='NOT_TESTED'))
    finally:
        if server:server.should_exit=True
        if thread:thread.join(timeout=10)
        if worker and not worker.closed:worker.close(15)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('live','cache','realtime'),required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--port',type=int,default=8765);p.add_argument('--catalog',type=Path)
    p.add_argument('--parent',type=Path,default=default_parent())
    p.add_argument('--pc-prefix-config',type=Path)
    p.add_argument('--binary',type=Path)
    p.add_argument('--realtime-draft',action='store_true',help='also verify live misses when mode=cache')
    p.add_argument('--output-tokens',type=int,choices=(24,32))
    p.add_argument('--compact',action='store_true',help='select shorter original checker forms for live input')
    a=p.parse_args()
    if a.mode=='cache' and not a.catalog:p.error('cache mode requires --catalog')
    serve(a)
