"""Read-only fixed helper over pinned SSH; credentials stay in memory only."""
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
import zlib

ROOT = Path(__file__).resolve().parents[3]
PROMPT = b'__A10_READONLY_EVIDENCE_AUTH__:'


def plan(cleanup=False):
    helper = 'cleanup_prepl_isolated_once.py' if cleanup else 'read_isolated_result.py'
    code = (Path(__file__).parent / helper).read_bytes()
    pin = hashlib.sha256(code).hexdigest()
    blob = base64.b64encode(gzip.compress(code)).decode()
    command = ('sudo -S -p ' + PROMPT.decode() + ' /usr/bin/python3 -B -I -c "'
               "import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode('" + blob + "')); "
               "assert hashlib.sha256(b).hexdigest()=='" + pin + "'; "
               "exec(compile(b,'reviewed_" + helper + "','exec'))\"")
    known = ROOT / 'platform/qwen35/a10/board_ssh_known_hosts'
    if known.read_text().strip() != '192.168.2.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe':
        raise RuntimeError('SSH key changed')
    return ['C:/Windows/System32/OpenSSH/ssh.exe', '-T', '-o', 'BindAddress=192.168.2.1',
            '-o', f'UserKnownHostsFile={known.as_posix()}', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
            '-o', 'NumberOfPasswordPrompts=1', '-o', 'PubkeyAuthentication=no', 'ubuntu@192.168.2.2', command], pin


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument('--execute-readonly', action='store_true')
    scope.add_argument('--execute-authorized-prepl-cleanup', action='store_true')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    argv, pin = plan(args.execute_authorized_prepl_cleanup)
    if not args.execute_readonly and not args.execute_authorized_prepl_cleanup:
        print(json.dumps(dict(board_contact=False, helper_sha256=pin, argv=argv)))
        return 0
    args.output.mkdir()
    # stdout contains evidence only. OpenSSH authentication uses the console;
    # sudo has a separately verified stderr prompt and a hidden local response.
    with (args.output / 'stdout.json').open('xb') as out:
        child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=out, stderr=subprocess.PIPE)
        events = queue.Queue()

        def reader():
            while True:
                chunk = child.stderr.read(1)
                events.put(chunk)
                if not chunk:
                    return

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        err, answered = bytearray(), False
        while True:
            try:
                chunk = events.get(timeout=30)
            except queue.Empty:
                print('Read-only SSH still waiting; no board mutation.', flush=True)
                continue
            if not chunk:
                break
            err.extend(chunk)
            if err.endswith(PROMPT):
                if answered:
                    child.stdin.close()
                    raise RuntimeError('Repeated authentication prompt; no retry')
                secret = getpass.getpass('Verified board sudo; hidden credential: ')
                child.stdin.write(secret.encode() + b'\n'); child.stdin.flush()
                secret = None
                answered = True
        rc = child.wait()
        child.stdin.close()
    receipt = dict(argv=argv, helper_sha256=pin, exit_code=rc,
                   stderr=err.decode(errors='replace'), scope='authorized_prepl_cleanup' if args.execute_authorized_prepl_cleanup else 'readonly')
    with (args.output / 'fetch_receipt.json').open('x', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)
    if rc:
        raise RuntimeError('Read-only capture failed: ' + str(rc))
    data = json.loads((args.output / 'stdout.json').read_bytes())
    if args.execute_authorized_prepl_cleanup:
        print(json.dumps(data))
        return 0
    for name, entry in {**data['files'], 'kernel.raw.txt': data['kernel_log'], 'active_lease.json': data['active_lease']}.items():
        if entry is None:
            continue
        raw = zlib.decompress(base64.b64decode(entry['zlib_base64'], validate=True))
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise RuntimeError('Evidence hash differs')
        with (args.output / name).open('xb') as f:
            f.write(raw)
    summary = {k: v for k, v in data.items() if k not in ('files', 'kernel_log', 'active_lease')}
    with (args.output / 'state.json').open('x', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(dict(status='READONLY_EVIDENCE_FETCHED_HASH_VERIFIED', exit_code=rc, output=str(args.output))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
