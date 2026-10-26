"""Board S1 baseline only. Does not import XRT or change PL/driver/services."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,row):
    with Path(p).open('x',encoding='utf-8') as f:
        json.dump(row,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())


def main():
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((root/'deployment-manifest.json').read_text())
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release==manifest['kernel']=='6.8.12-a10irq2'
    assert boot==manifest['boot_id'] and sha('/etc/machine-id')==manifest['machine_sha256']
    assert manifest['PL_submissions_allowed']==0 and not Path('/sys/module/zocl').exists()
    sys.path.insert(0,str(root/'control'))
    from accelerator_release_gate_v2 import collect,require_no_users
    from kernel_log_gate import KernelLogGate
    gate=KernelLogGate();baseline=(root/'kernel-baseline.raw.txt').read_bytes().decode('utf-8')
    assert gate.observe(boot,baseline,manifest['kernel_baseline_sha256'])['allowed']
    out=root/'run-v1';out.mkdir(mode=0o700)
    lockpaths=(Path('/var/lock/kv260-a1/deployment.lock'),Path('/run/lock/patient-qwen-linear.lock'))
    locks=[]
    for path in lockpaths:
        fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(fd)
    central=Path('/var/lock/kv260-a1');active=central/'active';active.mkdir()
    save(active/'lease.json',dict(schema='A12_STEP06_CPU_ONLY_V1',owner='A',pid=os.getpid(),boot_id=boot,
         scope='CPU_REFERENCE_ONLY_NO_PL',window='a12-step06-cpu-20261023-v1',issued_monotonic_ns=time.monotonic_ns(),
         expires_monotonic_ns=time.monotonic_ns()+300_000_000_000,PL_submissions_allowed=0))
    lease_pin=sha(active/'lease.json');observations=[];health_events=[];child=None;stopped=False
    def kernel():
        r=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3)
        assert r.returncode==0 and not r.stderr
        raw=r.stdout.decode('utf-8');g=gate.observe(boot,raw);assert g['allowed'],g
        return raw
    def health():
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot and sha(active/'lease.json')==lease_pin
        assert not Path('/sys/module/zocl').exists()
        temps=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
        mem={s.split(':')[0]:int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
        row=dict(monotonic_ns=time.monotonic_ns(),temperatures_mC=temps,
                 memory_kib={k:mem[k] for k in ('MemAvailable','CmaFree','CmaTotal')})
        health_events.append(row)
        assert temps and all(0<t<55000 for t in temps) and mem['MemAvailable']>=1048576 and mem['CmaFree']>=32768,'health reserve'
        return row
    def observe():
        if child is None or child.poll() is not None:return
        p=Path('/proc')/str(child.pid)
        try:
            status=(p/'status').read_text();smaps=(p/'smaps_rollup').read_text();maps=(p/'maps').read_text()
        except FileNotFoundError:return
        assert 'libxrt_' not in maps and 'libsp_linear_a12_trial' not in maps,'CPU worker mapped FPGA runtime'
        for fd in (p/'fd').iterdir():
            try:target=os.readlink(fd)
            except FileNotFoundError:continue
            assert not target.startswith(('/dev/dri/','/dev/xclmgmt','/dev/zocl','/dev/mem')),'CPU worker opened device'
        observations.append(dict(monotonic_ns=time.monotonic_ns(),status=status,smaps_rollup=smaps))
    def park(reason):
        save(out/'STOP.json',dict(reason=reason,lease_retained=True,no_kill=True,PL_submissions=0))
        print(json.dumps(dict(status='ISOLATED_CPU_WINDOW',reason=reason)),flush=True)
        while True:time.sleep(1)
    try:
        health();kernel();s=collect(allow_ps_display=True);require_no_users(s,True,boot_id=boot);save(out/'scan-before.json',s)
        env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_','GGML_','OMP_'))}
        env.update(LD_LIBRARY_PATH=str(root/'runtime'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
        binary=root/'runtime/qwen35-a12';os.chmod(binary,0o700)
        model=Path('/opt/patient-qwen/artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf')
        args=[str(binary),str(model),'2','1024','all','TILED','2','8']
        err=(out/'worker.stderr.txt').open('x');wire=(out/'worker.stdout.jsonl').open('x')
        child=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',env=env,bufsize=1)
        save(out/'worker-identity.json',dict(pid=child.pid,manager_pid=os.getpid(),argv=args,binary_sha256=sha(binary),physical_domain='BOARD',PL_submissions_allowed=0))
        q=queue.Queue()
        def reader():
            for line in child.stdout:wire.write(line);wire.flush();q.put(json.loads(line))
            q.put(None)
        reader_thread=threading.Thread(target=reader,daemon=True);reader_thread.start()
        def receive(seconds=90):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                health();observe()
                try:r=q.get(timeout=.25)
                except queue.Empty:continue
                assert r is not None,'unexpected CPU worker EOF'
                return r
            child.send_signal(signal.SIGUSR1)
            raise RuntimeError('CPU deadline; cancellation requested, no forced termination')
        ready=receive();assert ready['type']=='ready' and ready['execution_kind']=='CPU_REFERENCE'
        assert ready['bridge']['weight_count']==72 and ready['bridge']['weight_load_count']==72
        assert ready['bridge']['a12_route']['scope']=='none' and ready['bridge']['hardware_done_count'] is None
        save(out/'ready.json',ready);kernel()
        requests=json.loads((root/'control/requests.json').read_text());results=[]
        for req in requests:
            health();kernel();req=dict(req)
            if req.pop('diagnostic',False):
                req.update(diagnostic_dir=str(out/('diag-'+req['id'])),diagnostic_all_layers=False,
                           diagnostic_report=True,state_fingerprint=True,dump_state=True)
            child.stdin.write(json.dumps(req,ensure_ascii=False)+'\n');child.stdin.flush()
            while True:
                r=receive()
                if r['type'] in ('result','error'):break
            save(out/(req['id']+'-result.json'),r);results.append(r)
            assert r['type']=='result' and r['status']=='OK',r
            assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1 and r['gpu_layers']==0
            assert r['bridge']['weight_load_count']==72 and r['bridge']['hardware_done_count'] is None
            if not req.get('teacher_tokens'):assert r['text'].strip(),'empty natural text'
        child.stdin.write('{"op":"shutdown"}\n');child.stdin.flush();child.wait(timeout=10)
        assert child.returncode==0
        reader_thread.join(timeout=2);assert not reader_thread.is_alive()
        child.stdin.close();child.stdout.close();err.close();wire.close();health();kernel()
        scans=[]
        for attempt in range(4):
            snapshot=collect(allow_ps_display=True);scans.append(snapshot)
            try:require_no_users(snapshot,True,boot_id=boot);break
            except RuntimeError:
                if attempt==3:raise
                time.sleep(.1)
        save(out/'scans-after.json',scans)
        assert not Path('/sys/module/zocl').exists()
        gdm=subprocess.run(['systemctl','is-active','gdm'],capture_output=True,text=True,timeout=3)
        assert gdm.returncode==0 and gdm.stdout.strip()=='active'
        overlays=Path('/sys/kernel/config/device-tree/overlays')
        assert any(p.name.startswith('k26-starter-kits') and (p/'status').read_text().strip()=='applied' for p in overlays.iterdir())
        save(out/'observations.json',observations);save(out/'health.json',health_events)
        raw=kernel();(out/'kernel-final.raw.txt').write_text(raw)
        save(out/'result.json',dict(status='PASS_BOARD_CPU_S1_FUNCTION_AND_NORMAL_EXIT',physical_domain='BOARD',
            worker_report_domain_note='Raw inherited native PC label is retained; actual ARM execution proven by this board wrapper',
            boot_id=boot,kernel=os.uname().release,worker_exit_code=child.returncode,
            cases=[r['id'] for r in results],hardware_submissions=0,hardware_completions=0,
            implicit_XRT_BO_bytes=None,PL_numeric='NOT_TESTED',board_speedup=None))
        history=central/'history/a12-step06-cpu-20261023-v1';assert not history.exists()
        active.rename(history)
        for fd in reversed(locks):os.close(fd)
        print(json.dumps(dict(status='PASS_BOARD_CPU_S1_FUNCTION_AND_NORMAL_EXIT',lease_archived=True)),flush=True)
    except BaseException as exc:park(type(exc).__name__+': '+str(exc))


if __name__=='__main__':main()
