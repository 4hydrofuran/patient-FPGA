import fcntl,json,os,signal,subprocess,sys,time,urllib.request
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v3');bundle=root/'bundle';central=Path('/var/lock/kv260-a1');active=central/'active'
raw=(active/'lease.json').read_bytes();lease=json.loads(raw);pid=lease['pid'];proc=Path('/proc')/str(pid)
assert lease['window']=='a12-manual-web-20261026-v3' and str(root/'interactive_entry.py').encode() in (proc/'cmdline').read_bytes()
status=json.load(urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=3))
assert status['current_session_id'] is None and not status['busy']
worker_dir=bundle/'run-v1/s2/worker'
messages=[json.loads(l) for l in (worker_dir/'stdout.jsonl').read_text().splitlines()]
assert messages[-1]['type']=='cache_created' and messages[-1]['status']=='OK'
identity=json.loads((bundle/'run-v1/s2/identity.json').read_text());wp=Path('/proc')/str(identity['pid'])
assert (wp/'exe').resolve()==bundle/'bin/qwen35-a12'
pipe=os.readlink(wp/'fd/0')
fds=[p for p in (proc/'fd').iterdir() if os.readlink(p)==pipe]
assert len(fds)==1
fd=os.open(fds[0],os.O_WRONLY);os.write(fd,b'{"op":"shutdown"}\n');os.close(fd)
exitcode=None
for _ in range(150):
    stat=(wp/'stat').read_text().rsplit(')',1)[1].split()
    if stat[0]=='Z':exitcode=int(stat[49]);break
    time.sleep(.1)
assert exitcode==0
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
    run(['dfx-mgr-client','-remove',handle]);run(['rmmod','zocl']);run(['dfx-mgr-client','-load','k26-starter-kits'])
    assert not Path('/sys/module/zocl').exists()
    overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir()}
    assert overlays=={'k26-starter-kits_image_1':'applied'}
    active.rename(central/'history/a12-manual-web-20261026-v3-warmed-normal-close')
finally:
    for fd in locks:os.close(fd)
r=dict(status='WARMED_WORKER_NORMAL_PROTOCOL_EXIT',worker_exit=exitcode,commands=commands,model_questions=0,original_manager_finish_claimed=False,overlays=overlays)
(root/'warmed-close.json').write_text(json.dumps(r))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
