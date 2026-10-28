"""Explicit fixed-action SSH transport for the authorized cleanup-only window.

Default PLAN_ONLY. No password arguments/files; only verified hidden challenges.
Never retry/restart/kill remote work on transport failure or timeout.
"""
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
import zlib
from cleanup_window_v3_remote import PIN, INSTALL, READY, validate_payload

ROOT=Path(__file__).resolve().parents[3]
EVIDENCE=ROOT/'evidence/mlp_board_A/20261023-cleanup-pc-fix-v3'
PROMPT=b'__A11_CLEANUP_V3_AUTH__:'
AUTH='user-cleanup-only-20261023-v3-initial'


def candidate_payload():
    package=json.loads((EVIDENCE/'PACKAGE.json').read_bytes())
    archive=ROOT/package['archive']['path']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==package['archive']['sha256']
    candidate=EVIDENCE/'candidate/cleanup-v3-20261023'
    payload={p.name:base64.b64encode(p.read_bytes()).decode() for p in candidate.iterdir() if p.is_file()}
    validate_payload(payload)
    return json.dumps(payload).encode()+b'\n'


def plan(action, authorization_id=None, generation=None):
    if action in ('stage','readback'):
        code=(Path(__file__).parent/'cleanup_window_v3_remote.py').read_bytes()
        pin=hashlib.sha256(code).hexdigest()
        blob=base64.b64encode(gzip.compress(code)).decode()
        program=('import base64,gzip,hashlib,sys; b=gzip.decompress(base64.b64decode(\''+blob+'\')); '
            'assert hashlib.sha256(b).hexdigest()==\''+pin+'\'; sys.argv=[\'reviewed_cleanup_window\',\''+action+'\']; '
            'exec(compile(b,\'reviewed_cleanup_window_v3_remote.py\',\'exec\'))')
        command='sudo -S -p '+PROMPT.decode()+' /usr/bin/python3 -B -I -c "'+program+'"'
    else:
        manifest=json.loads((EVIDENCE/'candidate/cleanup-v3-20261023/candidate.json').read_bytes())
        source='cleanup_board_v3.py' if action=='launch' else 'cleanup_control_v3.py'
        pin=manifest['files'][source]['sha256']
        # Each fixed file is checked again before executing a path on the board.
        remote_path=(INSTALL/source).as_posix()  # Remote Linux, even on Windows host.
        args=[remote_path]
        if action=='launch': args+=['--execute-authorized-takeover','--authorization-id',AUTH,'--bundle-sha256',PIN]
        elif action=='status': args+=['--status']
        elif action=='resume':
            import re
            assert type(generation) is int and generation>=1
            assert authorization_id and re.fullmatch(r'[A-Za-z0-9_-]{8,80}',authorization_id)
            args+=['--resume-authorized','--authorization-id',authorization_id,'--generation',str(generation)]
        else: raise ValueError('unknown fixed action')
        program=('import os,hashlib; from pathlib import Path; p=Path(\''+remote_path+'\'); '
            's=p.lstat(); assert not p.is_symlink() and s.st_uid==0 and not s.st_mode&18; '
            'assert hashlib.sha256(p.read_bytes()).hexdigest()==\''+pin+'\'; '
            "os.execv('/usr/bin/python3',"+repr(['/usr/bin/python3','-B','-I',*args])+")")
        command='sudo -S -p '+PROMPT.decode()+' /usr/bin/python3 -B -I -c "'+program+'"'
    known=ROOT/'platform/qwen35/a10/board_ssh_known_hosts'
    assert known.read_text().strip()=='192.168.2.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe'
    argv=['C:/Windows/System32/OpenSSH/ssh.exe','-T','-o','BindAddress=192.168.2.1',
        '-o','UserKnownHostsFile='+known.as_posix(),'-o','StrictHostKeyChecking=yes',
        '-o','ConnectTimeout=5','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',
        '-o','NumberOfPasswordPrompts=1','-o','PubkeyAuthentication=no','ubuntu@192.168.2.2',command]
    return argv,pin


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--action',choices=('stage','launch','status','resume','readback'),required=True)
    ap.add_argument('--execute-authorized',action='store_true')
    ap.add_argument('--authorization-id');ap.add_argument('--generation',type=int)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();argv,pin=plan(a.action,a.authorization_id,a.generation)
    payload=candidate_payload() if a.action=='stage' else None
    if not a.execute_authorized:
        print(json.dumps(dict(mode='PLAN_ONLY',board_contact=False,action=a.action,helper_sha256=pin,
            payload_bytes=len(payload) if payload else 0,argv=argv)));return 0
    a.output.mkdir(exist_ok=False)
    with (a.output/'reservation.json').open('x') as f:
        json.dump(dict(status='RESERVED_NOT_COMPLETED',argv=argv,helper_sha256=pin,scope='CLEANUP_ONLY',action=a.action),f,indent=2)
    events=queue.Queue()
    with (a.output/'stdout.jsonl').open('xb') as output:
        child=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def out_reader():
            for line in iter(child.stdout.readline,b''): events.put(('out',line))
            events.put(('out',b''))
        def err_reader():
            for c in iter(lambda:child.stderr.read(1),b''): events.put(('err',c))
            events.put(('err',b''))
        threads=[threading.Thread(target=f,daemon=True) for f in (out_reader,err_reader)]
        for t in threads:t.start()
        err=bytearray(); answered=sent=False; ended=set()
        while len(ended)<2:
            try:kind,data=events.get(timeout=20)
            except queue.Empty:
                print('Awaiting remote status; no retry, termination or replay.',flush=True);continue
            if not data: ended.add(kind);continue
            if kind=='out':
                output.write(data);output.flush()
                if data.strip()==READY.encode():
                    assert a.action=='stage' and not sent
                    child.stdin.write(payload);child.stdin.flush();sent=True
                if a.action!='readback': print(data.decode(errors='replace').rstrip(),flush=True)
            else:
                err.extend(data)
                if err.endswith(PROMPT):
                    if answered: raise RuntimeError('Repeated sudo challenge; no retry')
                    secret=getpass.getpass('Verified board sudo; hidden credential: ')
                    child.stdin.write(secret.encode()+b'\n');child.stdin.flush();secret=None;answered=True
        rc=child.wait();child.stdin.close()
    with (a.output/'receipt.json').open('x') as f:
        json.dump(dict(action=a.action,exit_code=rc,helper_sha256=pin,stderr=err.decode(errors='replace'),
            payload_sent=sent,scope='CLEANUP_ONLY',completion='remote exit does not imply A11 pass'),f,indent=2)
    if rc==0 and a.action=='readback':
        data=json.loads((a.output/'stdout.jsonl').read_bytes())
        for name,item in {**data['files'],'kernel.raw.txt':data['kernel_log']}.items():
            if item is None:continue
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
            raw=zlib.decompress(base64.b64decode(item['zlib_base64'],validate=True))
            assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
            p=a.output/name;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f:f.write(raw)
        with (a.output/'state.json').open('x') as f:
            json.dump({k:v for k,v in data.items() if k not in ('files','kernel_log')},f,indent=2)
    print(json.dumps(dict(action=a.action,exit_code=rc,output=str(a.output))),flush=True)
    return 0 if rc==0 else 1


if __name__=='__main__':raise SystemExit(main())
