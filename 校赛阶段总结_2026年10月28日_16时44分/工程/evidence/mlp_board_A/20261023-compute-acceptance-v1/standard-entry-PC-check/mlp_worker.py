"""Only the reviewed A11 manager may start this persistent native child."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from mlp_engine import NativeAPI,run_plan
from mlp_policy import (CENTRAL,LIBRARIES,PLAN_SHA,digest,load_json,need,trusted_file,validate_review,verify_bundle,verify_owner)
from kernel_log_gate import KernelLogGate


def write(path,obj):
    pending=path.with_name(path.name+'.pending')
    with pending.open('x',encoding='utf-8') as f:
        json.dump(obj,f);f.flush();os.fsync(f.fileno())
    os.link(pending,path)  # atomic publication, refuses an existing target
    pending.unlink()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--a11-boundary-request',required=True)
    ap.add_argument('--a11-boundary-result',type=Path,required=True)
    args=ap.parse_args();source=args.source.resolve();identity=json.loads(args.a11_boundary_request)
    review=validate_review(load_json(source/'review.json'))
    manifest=verify_bundle(source,review['bundle_sha256'])
    for name in manifest['files']:trusted_file(source/name)
    for name,pin in LIBRARIES.items():need(digest(name)==pin,'board XRT library changed')
    need(digest(source/'review.json')==identity['request_sha256'] and identity['plan_sha256']==PLAN_SHA,'changed request')
    verify_owner(identity,review,parent=True)
    trusted_file(source)
    need(args.a11_boundary_result==source/'worker-result.json','wrong result target')
    need(digest(source/'worker-baseline.json')==identity['worker_baseline_sha256'],'changed worker baseline')
    baseline=load_json(source/'worker-baseline.json')
    for key in ('boot_id','window_id','manager_pid','lease_sha256','request_sha256'):
        need(baseline[key]==identity[key],'baseline identity differs')
    raw=(source/'worker-baseline.raw.txt').read_bytes().decode('utf-8')
    need(digest(source/'worker-baseline.raw.txt')==baseline['raw_sha256'] and baseline['kernel_gate_allowed'] is True and
         0<=time.monotonic_ns()-baseline['read_monotonic_ns']<=10_000_000_000,'stale worker baseline')
    gate=KernelLogGate();need(gate.observe(identity['boot_id'],raw,baseline['raw_sha256'])['allowed'],'bad baseline')
    signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM,signal.SIGHUP,signal.SIGQUIT})
    os.umask(0o077)
    write(source/'native-attempt.json',identity)
    (source/'outputs').mkdir();(source/'permits').mkdir(exist_ok=True)
    sequence=0
    def emit(event,**obj):
        if event in ('CONTEXT_OPENED','WEIGHT_LOADED'):
            obj['process_observation']=dict(status=Path('/proc/self/status').read_text(),
                smaps_rollup=Path('/proc/self/smaps_rollup').read_text(),meminfo=Path('/proc/meminfo').read_text(),
                accounting='PSS is process observation; CMA and BO are overlapping physical accounts, never sum',
                physical_bo_peak_bytes=None,implicit_xrt_allocations_bytes=None)
        print(json.dumps(dict(event=event,monotonic_ns=time.monotonic_ns(),**obj)),flush=True)
    def quarantine(reason,*retained):
        try:
            write(source/'STOP.json',dict(reason=reason,resources_retained=True))
            emit('WORKER_PARKED_NO_CLOSE',reason=reason)
        finally:
            while True:time.sleep(30)
    def checkpoint():
        verify_owner(identity,review,parent=True)
        need(not (source/'STOP.json').exists(),'parent stop latch')
        temps=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
        need(temps and all(0<t<55000 for t in temps),'temperature stop')
        mem={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()}
        need(mem['MemAvailable']>=1048576 and mem['CmaFree']>=32768,'memory reserve')
        p=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3)
        need(p.returncode==0 and not p.stderr,'kernel log unavailable')
        result=gate.observe(identity['boot_id'],p.stdout.decode('utf-8'))
        need(result['allowed'],'worker kernel gate: '+result['reason'])
        return dict(temperatures_mC=temps,memory_kib={k:mem[k] for k in ('MemAvailable','CmaFree')})
    def permit(phase,job):
        nonlocal sequence
        health=checkpoint();sequence+=1
        request=dict(identity,sequence=sequence,phase=phase,job=job)
        write(source/'permits'/f'ready-{sequence:03}.json',request)
        target=source/'permits'/f'allow-{sequence:03}.json';until=time.monotonic()+10
        while not target.exists():
            need(not (source/'STOP.json').exists() and time.monotonic()<until,'permit stop/deadline')
            time.sleep(.02)
        trusted_file(target);need(load_json(target)==request,'permit differs')
        checkpoint()
        emit('PERMIT_AND_HEALTH',sequence=sequence,phase=phase,job=job,**health)
    lease=load_json(CENTRAL/'active/lease.json')
    profile=load_json(source/'trial-profile-template.json')
    namefile=Path('/etc/xocl.txt')
    # XRT 2.18 edge board_name reads the first token of this file, or uses
    # "edge" when absent. Runtime API comparison in open() remains mandatory.
    if namefile.exists():
        trusted_file(namefile);tokens=namefile.read_text().split()
        need(tokens and len(tokens[0])<128,'empty/oversized XRT device name')
        profile['device_name']=tokens[0];profile['device_name_source_sha256']=digest(namefile)
    else:
        need(not namefile.is_symlink(),'dangling XRT name symlink')
        profile['device_name']='edge';profile['device_name_source_sha256']=None
    profile.update({k:identity[k] for k in ('boot_id','manager_pid','manager_start_ticks','inherited_device_lock_fd')})
    profile['expires_monotonic_ns']=lease['expires_monotonic_ns']
    write(source/'trial-profile.json',profile)
    try:
        api=NativeAPI(source)  # Only the child imports native XRT-dependent code.
        result=run_plan(api,source,load_json(source/'vectors/manifest.json'),permit,emit,quarantine)
        checkpoint()
        result.update(identity,worker_pid=os.getpid())
        write(args.a11_boundary_result,result)
    except BaseException as exc:quarantine(type(exc).__name__+': '+str(exc))
    return 0


if __name__=='__main__':raise SystemExit(main())
