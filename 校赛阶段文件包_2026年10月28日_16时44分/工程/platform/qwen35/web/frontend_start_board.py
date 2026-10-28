"""Plan by default. Explicit execution starts one fresh original-Owner web window."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def require_available_http_port(host='127.0.0.1', port=8000):
    import socket
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:probe.bind((host,port))
        except OSError as exc:
            raise RuntimeError('previous HTTP result view still owns the port; no new Owner started') from exc


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute-board',action='store_true')
    p.add_argument('--window-id',default='a12-b601e69ca-realtime-20261027-v1');a=p.parse_args()
    if not a.window_id.startswith('a12-') or not all(c.isalnum() or c=='-' for c in a.window_id):raise ValueError('fresh window name required')
    source=Path(__file__).resolve().parent
    target=Path('/var/lib/kv260-a12')/a.window_id.removeprefix('a12-')
    command=['/usr/bin/python3','-B',str(target/'continuous/fast_response_verify.py'),'--domain','BOARD',
        '--bundle',str(target),'--suite','web','--execute-board','--window-id',a.window_id]
    plan=dict(status='PLAN_ONLY',source=str(source),runtime_root=str(target),command=command,
        requires_kernel='6.8.12-a10irq2',temporary_lock='/run/lock/patient-qwen-linear.lock',
        temporary_rule='/run/udev/rules.d/71-patient-zocl-display.rules',
        first_actual_PL_web_answer=True,answer_cache=bool(json.loads((source/'continuous/web-config.json').read_text()).get('answer_cache')),BOARD='NOT_TESTED')
    if not a.execute_board:print(json.dumps(plan,indent=2));return
    if os.geteuid()!=0 or os.uname().machine!='aarch64' or os.uname().release!='6.8.12-a10irq2':raise RuntimeError('root/registered ARM64/irq2 required')
    machine=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
    if machine!='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec':raise RuntimeError('board identity differs')
    if Path('/var/lock/kv260-a1/active').exists() or Path('/sys/module/zocl').exists():raise RuntimeError('existing platform ownership requires handover')
    if target.exists():raise RuntimeError('window directory already exists; use a fresh name')
    require_available_http_port()
    subprocess.run(['/usr/bin/python3','-B',str(source/'continuous/fast_response_verify.py'),
        '--domain','PC','--bundle',str(source),'--suite','package'],check=True)
    sys.path[:0]=[str(source/'continuous'),str(source/'continuous/web_gateway/src')]
    from interactive_case import desktop_environment
    desktop_environment() # Require the user's Ubuntu desktop before acquiring any Owner.
    lock=Path('/run/lock/patient-qwen-linear.lock')
    if not lock.exists():
        fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
    rule=Path('/run/udev/rules.d/71-patient-zocl-display.rules')
    text='SUBSYSTEM=="drm", DRIVERS=="zocl-drm", TAG+="mutter-device-ignore"\n'
    if rule.exists() and rule.read_text()!=text:raise RuntimeError('existing display rule differs')
    if not rule.exists():rule.parent.mkdir(parents=True,exist_ok=True);rule.write_text(text)
    subprocess.run(['udevadm','control','--reload-rules'],check=True)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.zip'))
    with (target/'manager.stdout').open('xb') as out,(target/'manager.stderr').open('xb') as err:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
    receipt=dict(plan,status='STARTED_PENDING_READY_AND_BOARD_ACCEPTANCE',pid=process.pid,
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    (target/'STARTED.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
