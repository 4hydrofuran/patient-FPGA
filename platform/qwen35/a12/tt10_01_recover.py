"""Explicit recovery of this failed CPU-only window; never a compute retry.

Do not execute until user approves exact parked-manager retirement. Inspect is read-only.
Worker receives shutdown JSON, never a signal. SIGKILL is restricted to the verified
parked no-device manager after the CPU worker has a proven zero exit.
"""
import fcntl,hashlib,json,os,select,signal,subprocess,sys,time
from pathlib import Path

ROOT=Path('/var/lib/kv260-a12/tt10-01-20261024-v1')
REC=ROOT/'recovery-v1';CENTRAL=Path('/var/lock/kv260-a1')
LOCKS=(CENTRAL/'deployment.lock',Path('/run/lock/patient-qwen-linear.lock'))
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
BOOT='86e4938b-0f65-4166-9237-c547b67e1451'
MANAGER=167484;WORKER=167575
WORKER_SHA='b620bd89f278fa332cf4dc8a32ddebc817c5879b32dfe366d5022d4bf7a449b6'


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def j(p):return json.loads(Path(p).read_text())
def save(p,x):
    with Path(p).open('x') as f:json.dump(x,f);f.write('\n');f.flush();os.fsync(f.fileno())
def stat(pid):
    raw=(Path('/proc')/str(pid)/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
    return dict(raw=raw,state=fields[0],ppid=int(fields[1]),start_ticks=int(fields[19]),exit_code=int(fields[49]))
def fds(pid):return {p.name:os.readlink(p) for p in (Path('/proc')/str(pid)/'fd').iterdir()}


def lock_owners():
    answer={}
    for p in LOCKS:
        st=p.stat();key=(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino);rows=[]
        for line in Path('/proc/locks').read_text().splitlines():
            parts=line.split()
            for part in parts:
                if part.count(':')!=2:continue
                try:a,b,c=part.split(':');identity=(int(a,16),int(b,16),int(c))
                except ValueError:continue
                if identity==key:rows.append(dict(pid=int(parts[4]),kind=parts[1],mode=parts[3],raw=line))
        answer[str(p)]=rows
    return answer


def gates():
    assert os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release=='6.8.12-a10irq2'
    assert sha('/etc/machine-id')==MACHINE and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
    manifest=j(ROOT/'manifest.json');assert sha(ROOT/'manifest.json')==j(ROOT/'stage-receipt.json')['manifest_sha256']
    for row in manifest['files']:assert (ROOT/row['path']).stat().st_size==row['bytes'] and sha(ROOT/row['path'])==row['sha256']
    assert j(ROOT/'run-v1/s2/ISOLATED.json')['reason']=='HealthBlocked: full-model live extra reserve gate'
    assert not (ROOT/'run-v1/s2/worker').exists() and not (ROOT/'run-v1/s2/runtime-route.json').exists()
    assert not Path('/sys/module/zocl').exists() and not Path('/lib/firmware/xilinx/a12-tt10-01-20261024-v1').exists()
    assert j(ROOT/'run-v1/s1/ready.json')['execution_kind']=='CPU_REFERENCE'
    ms=stat(MANAGER);assert ms['state']=='S'
    lease=j(CENTRAL/'active/lease.json')
    assert lease['pid']==MANAGER and lease['owner_start_ticks']==ms['start_ticks'] and lease['window']=='a12-tt10-01-20261024-v1'
    assert (Path('/proc')/str(MANAGER)/'cmdline').read_bytes().split(b'\0')==[b'/usr/bin/python3',b'-B',b'-I',str(ROOT/'control/tt10_01_manager.py').encode(),b'']
    assert 'libxrt_' not in (Path('/proc')/str(MANAGER)/'maps').read_text()
    for target in fds(MANAGER).values():assert not target.startswith(('/dev/dri/','/dev/xclmgmt','/dev/dma_heap/'))
    locks=lock_owners();assert all(len(v)==1 and v[0]['pid']==MANAGER and v[0]['kind']=='FLOCK' and v[0]['mode']=='WRITE' for v in locks.values())
    sys.path.insert(0,str(ROOT/'control/support'))
    from accelerator_release_gate_v2 import collect,require_no_users
    from kernel_log_gate import KernelLogGate
    scan=collect(allow_ps_display=True);require_no_users(scan,True,boot_id=BOOT)
    gate=KernelLogGate();baseline=(ROOT/'run-v1/baseline.raw.txt').read_text()
    assert gate.observe(BOOT,baseline)['allowed']
    raw=subprocess.check_output(['dmesg','--raw']).decode();assert gate.observe(BOOT,raw)['allowed']
    overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()}
    assert overlays=={'k26-starter-kits_image_1':'applied'} and Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    return dict(manager=ms,lease=lease,lease_sha256=sha(CENTRAL/'active/lease.json'),manifest_sha256=sha(ROOT/'manifest.json'),
        module_absent=True,no_accelerator_users=True,default_overlay=overlays,kernel_allowed=True,scan=scan,locks=locks,observed_monotonic_ns=time.monotonic_ns())


def main(mode):
    if mode=='inspect':print(json.dumps(dict(event='RECOVERY_READ_ONLY',snapshot=gates())),flush=True);return
    assert mode=='execute_user_approved'
    # This mode is launched only after the user approves the concrete recovery script.
    os.umask(0o077);REC.mkdir();guard=os.open(CENTRAL/'a12-finalize-coordinator.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    mpfd=os.pidfd_open(MANAGER);wpfd=os.pidfd_open(WORKER)
    before=gates();save(REC/'before.json',before)
    ws=stat(WORKER);assert ws['ppid']==MANAGER and ws['state']=='S'
    assert sha(Path('/proc')/str(WORKER)/'exe')==WORKER_SHA
    maps=(Path('/proc')/str(WORKER)/'maps').read_text()
    assert 'libxrt_' not in maps and 'libsp_linear_a12_trial' not in maps
    assert (Path('/proc')/str(WORKER)/'wchan').read_text().strip()=='pipe_read'
    last=None
    for line in (ROOT/'run-v1/s1/worker/stdout.jsonl').open():last=json.loads(line)
    assert last['type']=='cache_created' and last['id']=='warm_prefix' and last['status']=='OK' and last['state_cleared_before_response']
    wfds=fds(WORKER);assert not any(v.startswith('/dev/') and v!='/dev/null' for v in wfds.values())
    pipe=wfds['0'];assert pipe.startswith('pipe:[')
    matches=[p for p in (Path('/proc')/str(MANAGER)/'fd').iterdir() if os.readlink(p)==pipe]
    assert len(matches)==1
    save(REC/'cpu-shutdown-reserved.json',dict(pid=WORKER,start_ticks=ws['start_ticks'],method='one stdin shutdown JSON',signals=0,hardware_operations=0))
    fd=os.open(matches[0],os.O_WRONLY|os.O_NONBLOCK);payload=b'{"op":"shutdown"}\n';assert os.write(fd,payload)==len(payload);os.close(fd)
    poll=select.poll();poll.register(wpfd,select.POLLIN);assert poll.poll(15000),'CPU exit not proven; retain manager and lease'
    ws=stat(WORKER);assert ws['state']=='Z' and ws['exit_code']==0
    save(REC/'cpu-exit.json',dict(exit_code=0,zombie_waiting_for_parent_reap=True,stat=ws,signals=0))
    subprocess.run(['systemctl','start','gdm.service'],check=True,timeout=15)
    assert subprocess.check_output(['systemctl','is-active','gdm.service']).strip()==b'active'
    for _ in range(50):
        tasks=list((Path('/proc')/str(MANAGER)/'task').iterdir())
        if len(tasks)==1:break
        time.sleep(.1)
    assert len(tasks)==1
    child_ids=[int(x) for x in (tasks[0]/'children').read_text().split()]
    assert child_ids==[WORKER] and stat(WORKER)['state']=='Z' and stat(WORKER)['exit_code']==0
    fresh=gates();assert fresh['manager']['start_ticks']==before['manager']['start_ticks']
    assert fresh['lease_sha256']==before['lease_sha256']
    assert time.monotonic_ns()-fresh['observed_monotonic_ns']<5000000000
    save(REC/'manager-retirement-reserved.json',dict(snapshot=fresh,signal=int(signal.SIGKILL),
        reason='Known parked no-device manager masks normal stop and CPU worker was never registered in its finalize IPC; only child is proven zero-exit CPU zombie',
        normal_manager_exit=False,worker_exit_code=0,hardware_operations=0,new_computation=0))
    signal.pidfd_send_signal(mpfd,signal.SIGKILL,None,0)
    poll=select.poll();poll.register(mpfd,select.POLLIN);assert poll.poll(5000),'No second signal; retain lease'
    locks=[]
    for path in LOCKS:
        fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(fd)
    assert not Path('/sys/module/zocl').exists() and sha(CENTRAL/'active/lease.json')==before['lease_sha256']
    scan=gates_after_exit()
    archive=CENTRAL/'history/a12-tt10-01-20261024-v1-failed-cpu-retired';assert not archive.exists()
    save(REC/'result.json',dict(status='FAILED_CPU_WINDOW_RECOVERED_MANAGER_ABNORMAL_EXIT_PRESERVED',manager_exit=-9,worker_exit=0,
        actual_PL_calls=0,new_computation=0,hardware_operations=0,lease_sha256=before['lease_sha256'],archive=str(archive),postcheck=scan))
    (CENTRAL/'active').rename(archive)
    for fd in reversed(locks):os.close(fd)
    os.close(mpfd);os.close(wpfd);os.close(guard)
    print(json.dumps(dict(event='RECOVERY_DONE',result=j(REC/'result.json'))),flush=True)


def gates_after_exit():
    from accelerator_release_gate_v2 import collect,require_no_users
    assert not Path('/sys/module/zocl').exists()
    scan=collect(allow_ps_display=True);require_no_users(scan,True,boot_id=BOOT)
    assert subprocess.check_output(['systemctl','is-active','gdm.service']).strip()==b'active'
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()}
    assert overlays=={'k26-starter-kits_image_1':'applied'}
    from kernel_log_gate import KernelLogGate
    gate=KernelLogGate();assert gate.observe(BOOT,(ROOT/'run-v1/baseline.raw.txt').read_text())['allowed']
    assert gate.observe(BOOT,subprocess.check_output(['dmesg','--raw']).decode())['allowed']
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
    assert all(len(v)==1 and v[0]['pid']==os.getpid() for v in lock_owners().values())
    return dict(scan=scan,default_overlay=overlays,gdm_active=True,module_absent=True)


if __name__=='__main__':main('inspect')
