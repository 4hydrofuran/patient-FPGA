"""Pinned SSH transport for the specifically authorized cleanup, default PLAN_ONLY."""
import argparse
import base64
import getpass
import gzip
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

ROOT=Path(__file__).resolve().parents[3]
PROMPT=b'__A11_RECOVERY_CONTINUATION_AUTH__:'


def plan():
    code=(Path(__file__).parent/'recover_cleanup_waiter.py').read_bytes()
    pin=hashlib.sha256(code).hexdigest()
    blob=base64.b64encode(gzip.compress(code)).decode()
    command=('sudo -S -p '+PROMPT.decode()+' /usr/bin/python3 -B -I -c "'
        "import base64,gzip,hashlib,sys; b=gzip.decompress(base64.b64decode('"+blob+"')); "
        "assert hashlib.sha256(b).hexdigest()=='"+pin+"'; "
        "sys.argv=['reviewed_cleanup','--execute-authorized-cleanup-only']; "
        "exec(compile(b,'reviewed_recover_cleanup_waiter.py','exec'))\"")
    known=ROOT/'platform/qwen35/a10/board_ssh_known_hosts'
    if known.read_text().strip()!='192.168.2.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe':
        raise RuntimeError('SSH key changed')
    return ['C:/Windows/System32/OpenSSH/ssh.exe','-T','-o','BindAddress=192.168.2.1',
        '-o','UserKnownHostsFile='+known.as_posix(),'-o','StrictHostKeyChecking=yes',
        '-o','ConnectTimeout=5','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',
        '-o','NumberOfPasswordPrompts=1','-o','PubkeyAuthentication=no','ubuntu@192.168.2.2',command],pin


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-authorized-cleanup-only',action='store_true')
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();argv,pin=plan()
    if not args.execute_authorized_cleanup_only:
        print(json.dumps(dict(board_contact=False,helper_sha256=pin,argv=argv)));return 0
    args.output.mkdir(exist_ok=False)
    receipt=args.output/'host_receipt.json'
    with receipt.open('x') as f:json.dump(dict(status='RESERVED_NOT_COMPLETED',exit_code=None,helper_sha256=pin,argv=argv),f)
    events=queue.Queue()
    with (args.output/'stdout.jsonl').open('xb') as output:
        child=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def stdout_reader():
            for line in iter(child.stdout.readline,b''):
                output.write(line);output.flush()
                print(line.decode(errors='replace').rstrip(),flush=True)
        def stderr_reader():
            while True:
                chunk=child.stderr.read(1);events.put(chunk)
                if not chunk:return
        reader=threading.Thread(target=stdout_reader);reader.start()
        err_reader=threading.Thread(target=stderr_reader,daemon=True);err_reader.start()
        err=bytearray();answered=False
        while True:
            try:chunk=events.get(timeout=30)
            except queue.Empty:
                print('Cleanup transport awaiting completion; no automatic retry/kill.',flush=True);continue
            if not chunk:break
            err.extend(chunk)
            if err.endswith(PROMPT):
                if answered:raise RuntimeError('Repeated sudo prompt; no retry')
                secret=getpass.getpass('Verified board cleanup sudo; hidden credential: ')
                child.stdin.write(secret.encode()+b'\n');child.stdin.flush();secret=None;answered=True
        rc=child.wait();reader.join();child.stdin.close()
    receipt.write_text(json.dumps(dict(status='REMOTE_EXITED' if rc==0 else 'STOPPED',exit_code=rc,
        helper_sha256=pin,argv=argv,stderr=err.decode(errors='replace'),scope='USER_ALLOWED_CLEANUP_ONLY'),indent=2))
    print(json.dumps(dict(exit_code=rc,receipt=str(receipt))));return rc


if __name__=='__main__':raise SystemExit(main())
