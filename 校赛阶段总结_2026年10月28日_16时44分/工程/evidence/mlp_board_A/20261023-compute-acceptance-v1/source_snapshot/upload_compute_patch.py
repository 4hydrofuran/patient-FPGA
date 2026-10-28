"""Exclusive user staging via the existing pinned SSH target; no board execution."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from fetch_single_result import plan
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--patch',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True)
    a=ap.parse_args();ssh,_=plan();ssh=ssh[:-1]
    dest='/home/ubuntu/a11-compute-patch-20261023-v1'
    guard="test \"$(cat /proc/sys/kernel/random/boot_id)\" = 8422f92f-d01f-4849-ad19-6e66b640a9ad && test \"$(uname -r)\" = 6.8.12-a10irq2 && test ! -d /sys/module/zocl && test ! -e /var/lock/kv260-a1/active && umask 077 && mkdir "+dest
    opts=ssh[2:-1]
    commands=[ssh+[guard],['C:/Windows/System32/OpenSSH/scp.exe',*opts,str(a.patch),'ubuntu@192.168.2.2:'+dest+'/patch.json.gz']]
    with a.receipt.open('x') as f:
        results=[]
        for argv in commands:
            rc=subprocess.run(argv).returncode;results.append(dict(argv=argv,exit_code=rc))
            if rc:break
        json.dump(dict(scope='STAGE_PATCH_NO_EXECUTION',commands=results),f,indent=2)
    return results[-1]['exit_code']
if __name__=='__main__':raise SystemExit(main())
