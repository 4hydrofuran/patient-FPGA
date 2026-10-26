import fcntl,json,os,signal,subprocess,sys,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v2');bundle=root/'bundle'
central=Path('/var/lock/kv260-a1');active=central/'active';raw=(active/'lease.json').read_bytes();lease=json.loads(raw);pid=lease['pid']
assert lease['window']=='a12-manual-web-20261026-v2' and pid==13152
proc=Path('/proc')/str(pid)
assert str(root/'interactive_entry.py').encode() in (proc/'cmdline').read_bytes()
assert not (bundle/'run-v1/s2/worker').exists() and not (proc/'task'/str(pid)/'children').read_text().strip()
sys.path.insert(0,str(bundle/'control/support'))
from accelerator_release_gate_v2 import collect,require_release
from idle_board_trial import active_handle
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
scan=collect(allow_ps_display=True);require_release(scan,int(Path('/sys/module/zocl/refcnt').read_text()),True,boot_id=boot)
fd=os.pidfd_open(pid);signal.pidfd_send_signal(fd,signal.SIGUSR1);os.close(fd)
for _ in range(50):
    if not proc.exists():break
    time.sleep(.1)
assert not proc.exists()
locks=[];commands=[]
try:
    for p in (central/'deployment.lock',Path('/run/lock/patient-qwen-linear.lock')):
        fd=os.open(p,os.O_RDWR);locks.append(fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert (active/'lease.json').read_bytes()==raw
    def run(args):
        p=subprocess.run(args,capture_output=True,text=True,timeout=12)
        commands.append(dict(argv=args,exit=p.returncode,stdout=p.stdout,stderr=p.stderr));assert p.returncode==0
        return p.stdout
    handle=active_handle(run(['dfx-mgr-client','-listPackage']),lease['window'])
    run(['dfx-mgr-client','-remove',handle])
    run(['rmmod','zocl'])
    run(['dfx-mgr-client','-load','k26-starter-kits'])
    assert not Path('/sys/module/zocl').exists()
    overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir()}
    assert overlays=={'k26-starter-kits_image_1':'applied'}
    active.rename(central/'history/a12-manual-web-20261026-v2-preworker-idle-close')
finally:
    for fd in locks:os.close(fd)
r=dict(status='OWN_PREWORKER_IDLE_PL_NORMAL_REMOVAL',commands=commands,worker_started=False,normal_worker_exit_claimed=False,overlays=overlays)
(root/'idle-close.json').write_text(json.dumps(r))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
