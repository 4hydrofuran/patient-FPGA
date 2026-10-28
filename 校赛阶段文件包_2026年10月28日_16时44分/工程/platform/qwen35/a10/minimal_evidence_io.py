"""Exclusive continuation transfer and evidence download; never runs board code."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
from idle_board_trial import digest, need
from minimal_package import ROOT, E, OUT, REMOTE

CONT = ROOT / 'platform/local/a10-minimal-continue-20261021-v1'
REMOTE_CONT = '/home/ubuntu/' + CONT.name
KNOWN = ROOT / 'platform/qwen35/a10/board_ssh_known_hosts'
OPTIONS = ['-o', 'BindAddress=192.168.2.1', '-o', 'UserKnownHostsFile=' + KNOWN.as_posix(),
           '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5',
           '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
           '-o', 'NumberOfPasswordPrompts=1', '-o', 'PubkeyAuthentication=no']
SSH, SCP = ['C:/Windows/System32/OpenSSH/' + n + '.exe' for n in ('ssh', 'scp')]


def prepare():
    CONT.mkdir()
    for name in ('minimal_continue.py', 'minimal_gate.py'):
        with (CONT / name).open('xb') as f:
            f.write((Path(__file__).parent / name).read_bytes())
    manifest = {p.name: digest(p) for p in CONT.iterdir()}
    with (CONT / 'continuation.manifest.json').open('x') as f:
        json.dump(manifest, f, indent=2)
    print(digest(CONT / 'continuation.manifest.json'))


def run_commands(commands, receipt):
    with receipt.open('x', encoding='utf-8') as f:
        for cmd in commands:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
            f.write(json.dumps(dict(argv=cmd, exit_code=p.returncode, stdout=p.stdout)) + '\n')
            f.flush()
            print(p.stdout, flush=True)
            need(p.returncode == 0, 'transfer stopped; no retry or board execution')


def upload(receipt):
    files = list(CONT.iterdir())
    verify = 'set -e; ' + '; '.join(
        "test \"$(sha256sum " + REMOTE_CONT + '/' + p.name +
        " | cut -d ' ' -f1)\" = " + digest(p) for p in files) + '; echo CONTINUATION_HASH_MATCH'
    run_commands([
        [SSH, '-T', *OPTIONS, 'ubuntu@192.168.2.2',
         'set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = 751e617d-c003-4b99-be03-bb5c78235d24; umask 077; mkdir ' + REMOTE_CONT],
        [SCP, *OPTIONS, *map(str, files), 'ubuntu@192.168.2.2:' + REMOTE_CONT + '/'],
        [SSH, '-T', *OPTIONS, 'ubuntu@192.168.2.2', verify]], receipt)


def download(receipt, failure_only=False):
    out = E / 'minimal-board-20261021-v1'
    out.mkdir()
    names = ('idle-result.jsonl',) if failure_only else ('idle-result.jsonl', 'compute.jsonl', 'approval.actual.json')
    paths = [REMOTE + '/' + n for n in names]
    paths += [REMOTE_CONT + '/continuation.jsonl']
    run_commands([
        [SSH, '-T', *OPTIONS, 'ubuntu@192.168.2.2', 'sha256sum ' + ' '.join(paths)],
        [SCP, *OPTIONS, *['ubuntu@192.168.2.2:' + p for p in paths], str(out)]], receipt)
    expected = {}
    for row in map(json.loads, receipt.read_text().splitlines()):
        if 'sha256sum ' not in row['argv'][-1]:
            continue
        expected = {Path(line.split()[1]).name: line.split()[0] for line in row['stdout'].splitlines()}
    need(expected and all(digest(out / name) == sha for name, sha in expected.items()),
         'download hashes differ')
    with (out / 'download_hashes.json').open('x') as f:
        json.dump(expected, f, indent=2)
    print('DOWNLOADED_HASHES_MATCH')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['prepare', 'upload', 'download', 'download-failure'])
    ap.add_argument('--receipt', type=Path)
    a = ap.parse_args()
    if a.mode == 'prepare':
        prepare()
    else:
        need(a.receipt is not None, 'exclusive receipt required')
        if a.mode == 'upload':
            upload(a.receipt)
        else:
            download(a.receipt, failure_only=a.mode == 'download-failure')
