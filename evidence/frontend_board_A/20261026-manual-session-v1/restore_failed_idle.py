import fcntl,json,os,signal,subprocess,sys,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v4');bundle=root/'bundle';central=Path('/var/lock/kv260-a1');active=central/'active'
raw=(active/'lease.json').read_bytes();lease=json.loads(raw);pid=lease['pid'];proc=Path('/proc')/str(pid)
assert lease['window']=='a12-manual-web-20261026-v4' and pid==15867
assert str(root/'interactive_entry.py').encode() in (proc/'cmdline').read_bytes()
fields=Path('/proc/16027/stat').read_text().rsplit(')',1)[1].split();assert fields[0]=='Z' and int(fields[49])==512
sys.path.insert(0,str(bundle/'control/support'))
from accelerator_release_gate_v2 import collect
from idle_board_trial import active_handle
def idle():
    scan=collect(allow_ps_display=True)
    assert scan['scan_complete'] and not scan['scan_issues'] and not scan['device_holders'] and not scan['device_mappings']
    assert int(Path('/sys/module/zocl/refcnt').read_text())==0
    return scan
before=idle()
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
    idle()
    def run(args):
        p=subprocess.run(args,capture_output=True,text=True,timeout=12)
        commands.append(dict(argv=args,exit=p.returncode,stdout=p.stdout,stderr=p.stderr));assert p.returncode==0
        return p.stdout
    h=active_handle(run(['dfx-mgr-client','-listPackage']),lease['window'])
    run(['dfx-mgr-client','-remove',h]);run(['rmmod','zocl']);run(['dfx-mgr-client','-load','k26-starter-kits'])
    assert not Path('/sys/module/zocl').exists()
    overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir()}
    assert overlays=={'k26-starter-kits_image_1':'applied'}
    active.rename(central/'history/a12-manual-web-20261026-v4-user-ended-failed')
finally:
    for fd in locks:os.close(fd)
r=dict(status='FAILED_MANUAL_SESSION_ENDED_IDLE_DEFAULT_RESTORED',worker_exit_code=2,raw_wait_status=512,worker_normal_exit=False,original_owner_finish=False,commands=commands,active_lease=False,zocl=False,overlays=overlays)
(root/'USER_EXIT_RESTORED.json').write_text(json.dumps(r))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
