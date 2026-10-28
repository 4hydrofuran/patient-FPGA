"""Run the prepared miss-only probe on the existing real x86 CPU model, locally."""
import argparse,copy,json,os,sys,time
from pathlib import Path


def run(a):
    root=a.bundle.resolve();window=root/'continuous';bundle=window/'bundle'
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    deps=json.loads((root/'PC_DEPENDENCIES.json').read_text())
    cfg=json.loads((root/'PC_PREFIX_CONFIG.json').read_text())
    for p in (bundle/'platform/qwen35/a12',window/'web_gateway/src',window):sys.path.insert(0,str(p))
    from supervisor import OwnedWorker
    from permission_hotpath import launch,policy
    from permission_probe import run as probe
    from board_case import load_native
    from fast_response_profile import load_profile,builder
    from interactive_case import CachedTransport
    from neutral_prefixes import warm_requests
    profile=copy.deepcopy(load_profile(window/'profile.json'))
    profile['prefix_identity']=cfg['identity'];profile['profile_model_requests']=True
    args=[deps['binary'],deps['model'],str(profile['threads']),'1024','all','TILED',str(profile['kernel_threads']),'8']
    command,launch_profile=launch(args,policy(bundle/'control/permission-runtime.json'))
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=deps['library_dir'],SP_TT10_CONFIG=str((root/'PC_PREFIX_CONFIG.json').resolve()),
        OMP_NUM_THREADS=str(profile['threads']),OPENBLAS_NUM_THREADS='1')
    worker=OwnedWorker(command,directory=out/'worker',env=env,health=lambda:None,max_runs=1,max_loads=1,
        expires=time.monotonic()+600,real=False)
    worker.worker_launch_profile=launch_profile
    try:
        ready=worker.get(120)
        if ready.get('execution_kind')!='CPU_REFERENCE':raise RuntimeError('PC CPU model required')
        before_nice=os.getpriority(os.PRIO_PROCESS,worker.process.pid)
        api=type('PC',(),{'receive':staticmethod(lambda w,*args,**kw:w.get(kw.get('timeout',180)))})()
        transport=CachedTransport(worker,None,out,api,profile=profile,maximum_questions=None)
        warm=json.loads((bundle/'control/requests.json').read_text())[1]
        for request in warm_requests(profile,warm):transport.warm(ready,request)
        native=load_native(window,Path(deps['project_root']))(transport,ready,max_output_tokens=profile['output_tokens'],
            domain='PC_REFERENCE',template_path=bundle/'control/chat_template.jinja',generation_strategy=profile['realtime_draft_strategy'])
        report=probe(native,worker,out/'permission-probe',prompt_builder=builder(profile),repeats=2)
        report.update(BOARD='NOT_TESTED',board_latency_ms=None,worker_nice_observed=before_nice,
            worker_pid=worker.process.pid,board_actions=0,real_model='EXISTING_X86_CPU_REFERENCE')
        if not worker.close(15):raise RuntimeError('PC worker did not exit normally')
        report['worker_exit_code']=worker.process.returncode
        (out/'RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(status='PASS_PC_REAL_FRESH_MODEL_PROBE',questions=len(report['rows']),nice=before_nice,
            answers=[r['answer'] for r in report['rows']],BOARD='NOT_TESTED'),ensure_ascii=False))
    finally:
        if not worker.closed:worker.close(15)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);run(p.parse_args())
