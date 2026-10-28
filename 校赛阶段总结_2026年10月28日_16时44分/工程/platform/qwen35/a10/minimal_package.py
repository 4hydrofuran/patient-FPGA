"""PC-only package/transfer helper. No board execution, secrets or installation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
from idle_board_trial import digest, need, HASHES

ROOT = Path(__file__).resolve().parents[3]
E = ROOT / 'evidence/board_platform/A10_20261018_intake'
OUT = ROOT / 'platform/local/a10-minimal-20261021-v1'
REMOTE = '/home/ubuntu/a10-minimal-20261021-v1'
SCRIPTS = ('minimal_trial.py', 'minimal_gate.py', 'idle_board_trial.py', 'kernel_log_gate.py')


def prepare():
    payload = {name: (Path(__file__).parent / name).read_bytes() for name in SCRIPTS}
    for name, sha in HASHES.items():
        p = ROOT / 'platform/build/a1-overlay-candidate-20260928' / name
        need(digest(p) == sha, 'test artifact differs')
        payload[name] = p.read_bytes()
    payload['shell.json'] = b'{"shell_type":"XRT_FLAT","num_pl_slots":1,"num_aie_slots":0}\n'
    host = ROOT / 'platform/build/a10-vadd-minimal-20261021-v1/a10-vadd-short'
    need(digest(host) == 'f7028cfab0ee6d0a9f5f7aa1200ae627e9ab1967346f7a4961e80067fb83ef5b',
         'unreviewed host build')
    payload['a10-vadd-short'] = host.read_bytes()
    bit = ROOT / 'platform/build/offline-link-kv260-vadd-20260928/vadd.xclbin'
    need(digest(bit) == '9d1243508f887dfe7db76ad1f37984907fe39567bab1cb118403f7691ed98394',
         'xclbin differs')
    payload['vadd.xclbin'] = bit.read_bytes()
    rows = [json.loads(l) for l in (E /
        'idle-window-closeout-v1/a10-candidate-idle-cleanup-20261021-v2.jsonl').read_text().splitlines()]
    raw = [r['raw_log'] for r in rows if r.get('event') == 'KERNEL_LOG_GATE'][-1]
    payload['baseline.raw.txt'] = raw.encode()
    need(hashlib.sha256(payload['baseline.raw.txt']).hexdigest() ==
         '9e568d2b6fcbb04548e13f2a4d263e8894bc89d22c4996b28a531b8936e79e3f',
         'baseline differs')
    manifest = dict(scope='USER_MAXIMAL_REDUCTION_ONE_N32_AFTER_IDLE_TEARDOWN',
                    files={n: dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
                           for n, b in payload.items()})
    OUT.mkdir()
    for name, data in payload.items():
        with (OUT / name).open('xb') as f:
            f.write(data)
    with (OUT / 'manifest.json').open('x', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(dict(bundle=str(OUT), manifest_sha256=digest(OUT / 'manifest.json'))))


def transfer(receipt):
    known = ROOT / 'platform/qwen35/a10/board_ssh_known_hosts'
    need(known.read_text().strip() ==
         '192.168.2.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe',
         'host key differs')
    manifest = json.loads((OUT / 'manifest.json').read_text())
    files = [OUT / n for n in manifest['files']] + [OUT / 'manifest.json']
    for name, entry in manifest['files'].items():
        need(digest(OUT / name) == entry['sha256'], 'payload changed')
    opts = ['-o', 'BindAddress=192.168.2.1', '-o', 'UserKnownHostsFile=' + known.as_posix(),
            '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5',
            '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
            '-o', 'NumberOfPasswordPrompts=1', '-o', 'PubkeyAuthentication=no']
    ssh, scp = ['C:/Windows/System32/OpenSSH/' + n + '.exe' for n in ('ssh', 'scp')]
    guard = ("set -e; test \"$(cat /proc/sys/kernel/random/boot_id)\" = "
             "751e617d-c003-4b99-be03-bb5c78235d24; test \"$(uname -r)\" = 6.8.12-a10irq1; "
             "test ! -d /sys/module/zocl; test ! -e /var/lock/kv260-a1/active; "
             "test -d /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1; "
             "umask 077; mkdir " + REMOTE)
    verify = 'set -e; ' + '; '.join(
        "test \"$(sha256sum " + REMOTE + '/' + p.name + " | cut -d ' ' -f1)\" = " + digest(p)
        for p in files) + '; chmod 755 ' + REMOTE + '/a10-vadd-short; ' + REMOTE + \
        '/a10-vadd-short --check-linkage; echo MINIMAL_TRANSFER_HASHES_VERIFIED'
    commands = [[ssh, '-T', *opts, 'ubuntu@192.168.2.2', guard],
                [scp, '-l', '32768', *opts, *map(str, files), 'ubuntu@192.168.2.2:' + REMOTE + '/'],
                [ssh, '-T', *opts, 'ubuntu@192.168.2.2', verify]]
    with receipt.open('x', encoding='utf-8') as f:
        for command in commands:
            p = subprocess.run(command, stdout=subprocess.PIPE, text=True)
            f.write(json.dumps(dict(argv=command, exit_code=p.returncode, stdout=p.stdout)) + '\n')
            f.flush()
            print(p.stdout, flush=True)
            need(p.returncode == 0, 'transfer/readback failed; no automatic retry')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--transfer-receipt', type=Path)
    a = ap.parse_args()
    if a.prepare:
        prepare()
    elif a.transfer_receipt:
        transfer(a.transfer_receipt)
    else:
        ap.print_help()
