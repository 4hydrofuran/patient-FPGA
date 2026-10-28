"""One additive, pinned-key upload. Default prints a plan, never connects."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from mlp_policy import MACHINE,digest,verify_bundle
PIN='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
BUNDLE=ROOT/'platform/local/a11-mlp-20261023-v1'
REMOTE='/home/ubuntu/a11-mlp-20261023-v1'


def plan(boot):
    assert str(uuid.UUID(boot))==boot
    man=verify_bundle(BUNDLE,PIN)
    known=ROOT/'platform/qwen35/a10/board_ssh_known_hosts'
    assert known.read_text().strip()=='192.168.2.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe'
    opts=['-o','BindAddress=192.168.2.1','-o',f'UserKnownHostsFile={known.as_posix()}',
          '-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=5','-o','ServerAliveInterval=5',
          '-o','ServerAliveCountMax=2','-o','NumberOfPasswordPrompts=1','-o','PubkeyAuthentication=no']
    guard=(f'set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}; test "$(uname -r)" = 6.8.12-a10irq2; '
        f'test "$(sha256sum /etc/machine-id | cut -d \' \' -f1)" = {MACHINE}; test "$(id -u)" = 1000; '
        'test ! -d /sys/module/zocl; test ! -e /var/lock/kv260-a1/active; ')
    ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-T',*opts,'ubuntu@192.168.2.2']
    paths=[str(p) for p in sorted(BUNDLE.iterdir())]
    hashes={n:e['sha256'] for n,e in man['files'].items()};hashes['manifest.json']=PIN
    return [ssh+[guard+'umask 077; mkdir '+REMOTE],
        ['C:/Windows/System32/OpenSSH/scp.exe','-r','-l','16384',*opts,*paths,'ubuntu@192.168.2.2:'+REMOTE+'/'],
        ssh+[guard+'cd '+REMOTE+'; find . -type f -exec sha256sum {} +']],hashes


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--boot-id',required=True)
    ap.add_argument('--execute-authorized-upload',action='store_true');ap.add_argument('--receipt',type=Path)
    args=ap.parse_args();commands,hashes=plan(args.boot_id)
    if not args.execute_authorized_upload:
        print(json.dumps(dict(board_contact=False,commands=commands,hashes=hashes),indent=2));sys.exit(0)
    assert args.receipt
    report=dict(status='RESERVED',board_execution=False,boot_id=args.boot_id,commands=[])
    with args.receipt.open('x',encoding='utf-8') as f:
        try:
            for command in commands:
                p=subprocess.run(command,stdout=subprocess.PIPE)
                output=p.stdout.decode('utf-8');report['commands'].append(dict(argv=command,exit_code=p.returncode,stdout=output))
                if p.returncode:raise RuntimeError('upload failed; no automatic retry')
            found={row.split()[1].removeprefix('./'):row.split()[0] for row in output.splitlines() if len(row.split())==2}
            assert found==hashes,'readback hashes differ'
            report['status']='UPLOADED_VERIFIED_NOT_EXECUTED'
        except BaseException as exc:report.update(status='STOPPED',error=str(exc))
        finally:json.dump(report,f,indent=2)
    print(report['status']);sys.exit(0 if report['status']=='UPLOADED_VERIFIED_NOT_EXECUTED' else 2)
