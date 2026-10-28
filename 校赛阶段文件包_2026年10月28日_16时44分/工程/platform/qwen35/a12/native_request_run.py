"""Run the frozen ordinary requests through an authentic PC model + permit adapter.

No board/ARM execution, heavy diagnostics, downloads or package installation.
"""
import argparse
import copy
from contextlib import nullcontext
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import time
from unittest import mock

from native_cpu_build import ROOT,OUT,WORK,sha,read,save
from native_request_journal import NativeJournalWorker,NativeRequestController,DOMAIN
from request_journal_verified import BUNDLE,FrozenProbe,digest,require
from resource_probe_policy import ordinary_comparison


def mapped_libraries(pid):
    result={}
    for line in (Path('/proc')/str(pid)/'maps').read_text().splitlines():
        name=line.split()[-1]
        if not name.startswith('/'):continue
        p=Path(name);base=p.name.split('.so.')[0]+'.so' if '.so.' in p.name else p.name
        if base.startswith(('libllama.','libggml','libsp_linear','liba12_native_cpu_control')):result[base]=sha(p)
    return result


def prepare_config(build):
    work=Path(build['workspace'])
    cpu_config=ROOT/'modules/linear_A/cpu_threads2_config.json'
    adapter=dict(schema='A12_NATIVE_CPU_CONTROL_V1',execution_kind='CPU_REFERENCE',
        contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',
        allow_device_access=False,cpu_library=build['existing_cpu_library'],
        cpu_library_sha256=build['existing_cpu_library_sha256'],cpu_config=str(cpu_config),cpu_config_sha256=sha(cpu_config))
    ap=work/'adapter-config.json';save(ap,adapter)
    route=dict(contract_sha256=adapter['contract_sha256'],fallback='disabled',fpga_required=True,scope='all',
        execution_kind='PC_MATH_DOUBLE',library=build['library'],library_sha256=build['library_sha256'],
        backend_config=str(ap),backend_config_sha256=sha(ap),trace_limit=4096)
    rp=work/'route-config.json';save(rp,route)
    prefix=read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02/prefix-config-PC.json')
    prefix['identity']['libraries']['liba12_native_cpu_control.so']=build['library_sha256']
    prefix['identity']['pc_adapter_config_sha256']=sha(ap)
    prefix['identity']['pc_route_config_sha256']=sha(rp)
    pp=work/'native-prefix-config.json';save(pp,prefix)
    return rp,pp


class PCOwner:
    def __init__(self,path):
        self.path=path;self.pid=os.getpid();self.fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
        fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.owner_calls=0;self.health_calls=0
    def check(self):
        self.owner_calls+=1;require(os.getpid()==self.pid,'PC manager changed')
        a=os.fstat(self.fd);b=self.path.stat();require((a.st_dev,a.st_ino)==(b.st_dev,b.st_ino),'PC lock replaced')
        text=Path('/proc/self/fdinfo',str(self.fd)).read_text()
        require('FLOCK' in text and str(self.pid) in text,'PC lock no longer owned')
    def health(self):
        self.health_calls+=1
        memory={line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()
                if line.startswith(('MemAvailable:','Cached:','Dirty:','Writeback:'))}
        require(memory['MemAvailable']>=1114112,'PC MemAvailable below original memory floor')
        return dict(domain='PC_LOCAL_MEMORY_ONLY',memory_kib=memory,board_CMA='NOT_AVAILABLE_PC')
    def close(self):os.close(self.fd)


def run(mode,tag,build_receipt=OUT/'BUILD.json',fault=None):
    require(os.name=='posix' and platform.machine().lower() in ('x86_64','amd64'),'PC x86 only')
    require(type(tag) is str and re.fullmatch('[A-Za-z0-9_-]{1,48}',tag),'invalid native run tag')
    os.umask(0o077);build=read(build_receipt);work=Path(build['workspace'])
    parent=read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02/RESULT.json')
    require(build['existing_native_sha256']==parent['native_sha256'] and
        build['existing_cpu_library_sha256']==parent['libraries']['libsp_linear_cpu.so'],'unreviewed native/CPU library')
    require(build['status']=='PASS_PC_ADAPTER_BUILD' and sha(build['library'])==build['library_sha256'] and
        sha(build['existing_native'])==build['existing_native_sha256'] and
        sha(build['existing_cpu_library'])==build['existing_cpu_library_sha256'],'build inputs changed')
    if not (work/'route-config.json').exists():prepare_config(build)
    route=work/'route-config.json';prefix=work/'native-prefix-config.json'
    directory=work/('run-'+tag);directory.mkdir(mode=0o700,exist_ok=False)
    evidence=OUT/('run-'+tag);evidence.mkdir(exist_ok=False)
    save(evidence/'SOURCE_AT_LAUNCH.json',[dict(path='platform/qwen35/a12/'+n,sha256=sha(ROOT/'platform/qwen35/a12'/n))
        for n in ('native_request_run.py','native_request_journal.py')])
    owner=PCOwner(directory/'pc-owner.lock');worker=None;failure=None
    frozen=FrozenProbe()
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(SP_A12_CONFIG=str(route),SP_TT10_CONFIG=str(prefix),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',
        LD_LIBRARY_PATH=str(Path(build['existing_cpu_library']).parent))
    argv=[build['existing_native'],str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8']
    start=time.monotonic_ns();injected=False;validated_answers=[];last_native=None
    try:
        worker=NativeJournalWorker(argv,directory=directory/'worker',env=env,inherited_fds=(owner.fd,),
            health=owner.health,owner_check=owner.check,max_runs=5000,max_loads=72,
            expires=time.monotonic()+900,real=False,journal_mode=mode)
        ready=worker.get(120);save(evidence/'ready.json',ready)
        libs=mapped_libraries(worker.process.pid);save(evidence/'LOADED_LIBRARIES.json',libs)
        expected=read(prefix)['identity']['libraries']
        require(libs==expected,'actual loaded native libraries differ from prefix identity')
        identity=dict(adapter_sha256=build['library_sha256'],cpu_library_sha256=build['existing_cpu_library_sha256'],
            native_sha256=build['existing_native_sha256'],route_config_sha256=sha(route),prefix_config_sha256=sha(prefix))
        controller=NativeRequestController(worker,ready,identity)
        # Import the same frozen application and clock helper as the ordinary package.
        import sys
        sys.path.insert(0,str(BUNDLE/'application'))
        helper=BUNDLE/'platform/qwen35/a12/tt10_00_app.py'
        spec=importlib.util.spec_from_file_location('native_journal_frozen_app',helper)
        app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
        results={};timings=[];summaries=[];active_folder=None
        def fault_scope(kind):
            if fault!=kind:return nullcontext()
            actual_fsync=os.fsync;target=worker._journal.fd
            def fail(fd):
                nonlocal injected
                if fd==target:
                    injected=True
                    raise OSError(errno.EIO,'PC injected '+kind+' on actual journal FD')
                return actual_fsync(fd)
            return mock.patch.object(os,'fsync',side_effect=fail)
        def receive():
            nonlocal last_native
            result=worker.get(180)
            if result.get('type')=='token':controller.accept_token(result)
            else:
                last_native=result
                save(active_folder/'result.json',result)
                with fault_scope('end_fsync'):
                    summary=controller.finish(result)
                save(active_folder/'verification.json',summary);summaries.append(summary)
            return result
        for name in ('app_R0','warm_prefix','app_hit'):
            request=controller.arm(name);active_folder=evidence/name;active_folder.mkdir()
            save(active_folder/'request.json',request)
            if fault=='health_submit' and name=='app_R0':
                def unhealthy():
                    nonlocal injected
                    injected=True
                    raise RuntimeError('PC injected fresh health failure before CPU submit')
                worker.health=unhealthy
            if 'application' in request:
                try:
                    with fault_scope('begin_fsync'):
                        result,events,_,_,clock=app.measure(controller,receive,frozen.template,request)
                except AssertionError as exc:
                    # The old clock helper masks Session backend errors as a
                    # missing-policy-baseline assertion. Keep that cause and
                    # expose the actual boundary failure without altering it.
                    if str(exc)=='policy response is not a model baseline' and worker._io_fault:
                        raise RuntimeError('native boundary failed: '+worker._io_fault) from exc
                    raise
                clock['cache']=result['prefix_cache_request'];clock['journal_mode']=mode
                save(active_folder/'application-timing.json',clock)
                require(clock['answer_source']=='MODEL' and clock['eos'] is True and
                    clock['candidate_check']['status']==clock['final_check']['status']=='pass','native application content failed')
                validated_answers.append(name)
                timings.append({k:clock[k] for k in ('TTFT_app_ms','complete_app_ms','cache','journal_mode')})
            else:controller.send(request);result=receive()
            results[name]=result
            print(json.dumps(dict(event='NATIVE_REQUEST_VERIFIED',mode=mode,id=name,
                cpu_calls=worker.runs,PL_calls=0)),flush=True)
        pair=ordinary_comparison(results['app_R0'],results['app_hit'])
        previous=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02'
        cpu_equal={name:ordinary_comparison(read(previous/name/'result.json'),results[name]) for name in ('app_R0','app_hit')}
        require(worker.close(timeout=15),'native PC worker did not close normally')
        require(not any(p.suffix in ('.bin','.f32') or p.name=='diag' for p in directory.rglob('*')),'raw diagnostic file found')
        journal=worker.directory/'events.jsonl'
        report=dict(status='PASS_ACTUAL_PC_MODEL_WITH_REQUEST_JOURNAL',domain=DOMAIN,journal_mode=mode,
            workspace=str(directory),worker_exit_code=worker.process.returncode,worker_closed=worker.closed,
            actual_cpu_permits=worker.runs,actual_cpu_weight_loads=worker.loads,
            owner_checks=owner.owner_calls,health_checks=owner.health_calls,
            journal_rows=worker._serial,journal_bytes=journal.stat().st_size,journal_sha256=sha(journal),
            permission_metrics=worker.permission_metrics,timing_PC_ONLY=timings,request_summaries=summaries,
            R0_hit_comparison=pair,original_CPU_comparison=cpu_equal,
            libraries=libs,native_identity=identity,raw_diagnostic_files=0,PL_calls=0,hardware_completions=None,
            BOARD='NOT_TESTED',board_latency_saving_s=None,board_CMA='NOT_TESTED',
            elapsed_PC_s=(time.monotonic_ns()-start)/1e9,fault_injection=fault,validated_answers=validated_answers)
        save(evidence/'RESULT.json',report);print(json.dumps(report,indent=2))
    except BaseException as exc:
        failure=type(exc).__name__+': '+str(exc)
        save(evidence/'FAILURE.json',dict(status='FAIL_RETAINED_NO_REPLAY',reason=failure,mode=mode,
            pid=worker.process.pid if worker else None,PL_calls=0,BOARD='NOT_TESTED',
            fault_injection=fault,fault_actually_injected=injected,validated_answers=validated_answers,
            permission_runs=worker.runs if worker else None,root_boundary_failure=worker._io_fault if worker else None,
            original_exception_cause=str(exc.__cause__) if exc.__cause__ else None,
            native_status=last_native.get('status') if last_native else None,
            native_state_cleared=last_native.get('state_cleared_before_response') if last_native else None,
            native_cpu_completed=last_native.get('bridge',{}).get('a12_route',{}).get('pc_verified_completions') if last_native else None))
        raise
    finally:
        if worker is not None and not worker.closed:
            # Exact pinned x86 PC executable rejects FPGA_REAL at native startup.
            # Failure remains latched. EOF requests a cooperative CPU exit only;
            # do not call this a normal close or a platform release.
            if worker.process.poll() is None:
                if not worker.process.stdin.closed:worker.process.stdin.close()
                try:worker.manager_sock.shutdown(__import__('socket').SHUT_WR)
                except OSError:pass
                try:worker.process.wait(timeout=15)
                except __import__('subprocess').TimeoutExpired:pass
            save(evidence/'CPU_FAILURE_CLOSE.json',dict(domain=DOMAIN,original_failure=failure,
                exit_code=worker.process.poll(),normal_close=False,forced_signal=False,platform_released=False))
        if worker is None or worker.process.poll() is not None:
            if worker is not None:
                worker.permission_thread.join(2);worker.reader_thread.join(2)
                for handle in (worker.stderr,worker.process.stdin,worker.process.stdout,worker.manager_sock):handle.close()
                if hasattr(worker,'_journal'):worker._journal.close()
            owner.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['strict','request'],required=True)
    p.add_argument('--tag',required=True);p.add_argument('--build',type=Path,default=OUT/'BUILD.json')
    p.add_argument('--fault',choices=['begin_fsync','end_fsync','health_submit'])
    a=p.parse_args();run(a.mode,a.tag,a.build,a.fault)
