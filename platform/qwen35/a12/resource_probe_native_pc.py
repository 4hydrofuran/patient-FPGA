"""Real x86 CPU request-flow check, not a PL/CMA/BOARD performance substitute."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from resource_probe_entry import sha, validate_bundle
from resource_probe_policy import ordinary_comparison, require, validate_plan
from resource_probe_prepare import ROOT, OUT
from supervisor import OwnedWorker


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, default=OUT/'bundle-v1')
    parser.add_argument('--binary', type=Path,
        default=Path('/home/member-a/kv260-build/a12-tt10-01-20261024-v1/pc04/qwen35-a12'))
    args=parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    validate_bundle(args.bundle)
    requests=json.loads((args.bundle/'control/requests.json').read_text(encoding='utf-8'))
    spec=json.loads((args.bundle/'control/window-spec.json').read_text(encoding='utf-8'))
    validate_plan(requests, spec)
    # Existing development dependencies only. No package installation or rebuild.
    prior=json.loads((ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json').read_text())
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=str(Path(prior['workspace'])/'pc'), OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')
    model=ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'
    argv=[str(args.binary),str(model),'2','1024','all','TILED','2','8']
    workers=[]
    def launch(folder, environment):
        worker=OwnedWorker(argv, directory=folder, env=environment, health=lambda:None,
                           max_runs=1, max_loads=1, expires=time.monotonic()+900, real=False)
        workers.append(worker)
        ready=worker.get(120)
        require(ready['type']=='ready' and ready['execution_kind']=='CPU_REFERENCE', 'PC native identity differs')
        return worker,ready
    try:
        probe,ready=launch(args.evidence/'identity-worker',env)
        libraries={}
        for line in (Path('/proc')/str(probe.process.pid)/'maps').read_text().splitlines():
            fields=line.split()
            if not fields or not fields[-1].startswith('/'):continue
            path=Path(fields[-1]);name=path.name.split('.so.')[0]+'.so' if '.so.' in path.name else path.name
            if name.startswith(('libllama.','libggml','libsp_linear')):
                libraries[name]=sha(path)
        require(bool(libraries), 'PC loaded library pins unavailable')
        require(probe.close(15), 'PC identity worker normal close failed')
        config=json.loads((args.bundle/'control/prefix-config.json').read_text(encoding='utf-8'))
        config['identity'].update(executable_sha256=sha(args.binary), libraries=libraries)
        save(args.evidence/'prefix-config-PC.json',config)
        env['SP_TT10_CONFIG']=str(args.evidence/'prefix-config-PC.json')
        worker,ready=launch(args.evidence/'ordinary-worker',env)
        save(args.evidence/'ready-PC.json',ready)
        require(ready['prefix_cache']['enabled'], 'PC prefix store disabled')
        binding=ready['prefix_cache']['binding_sha256']
        # Freeze the original application's prompt/checker; do not pick up the
        # current working tree's separately shortened, not-yet-accepted prompt.
        sys.path.insert(0,str(args.bundle/'application'))
        helper=args.bundle/'platform/qwen35/a12/tt10_00_app.py'
        module_spec=importlib.util.spec_from_file_location('probe_frozen_measured_app',helper)
        app=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(app)
        results={};timings=[]
        for original in requests:
            request=copy.deepcopy(original)
            if request['op']=='cache_create' or request['cache_policy']!='R0':
                request['cache_binding_sha256']=binding
            directory=args.evidence/request['id'];directory.mkdir()
            save(directory/'request.json',request)
            if 'application' in request:
                result,events,_,_,clock=app.measure(worker,lambda:worker.get(180),
                    (args.bundle/'control/chat_template.jinja').read_text(encoding='utf-8'),request)
                clock['cache']=result['prefix_cache_request']
                save(directory/'application-timing.json',clock)
                require(clock['answer_source']=='MODEL' and clock['eos'] and
                        clock['candidate_check']['status']==clock['final_check']['status']=='pass',
                        'PC ordinary answer/content check failed')
                timings.append({k:clock[k] for k in ['TTFT_app_ms','complete_app_ms','cache']})
            else:
                worker.send(request);result=worker.get(180)
            save(directory/'result.json',result)
            require(result['status']=='OK' and result['state_cleared_before_response'] is True and
                    result['state_position_after_clear']==-1, 'PC native clear failed')
            require(result['bridge'].get('execution_kind')=='CPU_REFERENCE', 'PC mode changed')
            if request['id']=='app_hit':
                require(result['prefix_cache_request']['hit'] is True and
                        result['prefix_cache_request']['new_tokens']==37, 'PC hit did not reuse frozen prefix')
            results[request['id']]=result
        comparison=ordinary_comparison(results['app_R0'],results['app_hit'])
        require(worker.close(15), 'PC ordinary worker normal close failed')
        require(not any(p.name=='diag' or p.suffix in ('.bin','.f32') for p in args.evidence.rglob('*')),
                'unexpected raw diagnostic file produced')
        report=dict(status='PASS_ACTUAL_CPU_NATIVE_ORDINARY_R0_WARM_HIT',domain='PC_X86_CPU_REFERENCE',
                    native_sha256=sha(args.binary),application_helper_sha256=sha(helper),libraries=libraries,
                    comparison=comparison,timing_PC_ONLY=timings,worker_exit_codes=[w.process.returncode for w in workers],
                    raw_diagnostic_files=0,new_PL_calls=0,BOARD='NOT_TESTED',CMA_recovery='NOT_TESTED',
                    full_intermediate_state='NOT_RETESTED',native_or_ARM_binary_rebuilt=False)
        save(args.evidence/'RESULT.json',report)
        print(json.dumps(report,ensure_ascii=True,indent=2))
    except BaseException as exc:
        save(args.evidence/'FAILURE.json',dict(status='FAIL',reason=type(exc).__name__+': '+str(exc),
             worker_pids=[w.process.pid for w in workers],BOARD='NOT_TESTED',retry=False))
        # CPU-only workers can close cooperatively; never use forced signals.
        for worker in workers:
            if not worker.closed:
                worker.close(15)
        raise


if __name__=='__main__':main()
