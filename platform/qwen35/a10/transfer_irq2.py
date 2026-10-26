"""Pinned bounded transfer/readback only. Never runs the staging installer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
from minimal_evidence_io import SSH, SCP, OPTIONS

LOCAL = Path('C:/Patientqwen/platform/local/a10-irq2-transfer-20261021-v1')
REMOTE = '/home/ubuntu/a10-irq2-stage-20261021-v1'
BOOT = 'bf3796f0-9785-4afd-a617-3ad578a24d10'
GUARD = ('set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = ' + BOOT +
         '; test "$(uname -r)" = 6.8.0-1015-xilinx; '
         'test "$(sha256sum /etc/machine-id | cut -d \' \' -f1)" = '
         'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec; '
         'test ! -d /sys/module/zocl; ')


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def hashes():
    m = json.loads((LOCAL / 'manifest.json').read_text())
    expected = {'candidate.fit', 'modules.tar.gz', 'stage_irq2_board.py',
                'stage_candidate_board.py', 'original_module_backup.py', 'original-backup-proof.json'}
    if set(m['hashes']) != expected or any(sha(LOCAL / n) != v for n, v in m['hashes'].items()):
        raise ValueError('Exact local transfer files changed')
    return m['hashes']


def run(cmd, log):
    # SSH credentials stay in the interactive terminal; never argv/env/receipt.
    result = subprocess.run(cmd, stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8', errors='replace')
    log.write(json.dumps(dict(argv=cmd, exit_code=result.returncode, stdout=output)) + '\n')
    log.flush()
    print(output, flush=True)
    if result.returncode:
        raise RuntimeError('Command failed; partials retained, no retry')
    return output


def verify(h, log):
    command = GUARD + 'cd ' + REMOTE + '; sha256sum ' + ' '.join(sorted(h))
    output = run([SSH, '-T', *OPTIONS, 'ubuntu@192.168.2.2', command], log)
    actual = {line.split()[1]:line.split()[0] for line in output.splitlines() if len(line.split()) == 2}
    if actual != h:
        raise ValueError('Remote byte hashes differ')
    with (LOCAL / 'upload-readback.json').open('x') as f:
        json.dump(dict(status='UPLOADED_HASH_VERIFIED_NOT_INSTALLED', hashes=h, boot_id=BOOT), f, indent=2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['upload', 'readback', 'download-result'])
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args()
    h = hashes()
    with a.receipt.open('x') as log:
        if a.mode == 'upload':
            run([SSH, '-T', *OPTIONS, 'ubuntu@192.168.2.2', GUARD +
                 'test ! -e /boot/firmware/a10-candidate-irq2-20261021.fit; '
                 'test ! -e /usr/lib/modules/6.8.12-a10irq2; umask 077; mkdir ' + REMOTE], log)
            run([SCP, '-l', '32768', *OPTIONS, *[(LOCAL / n).as_posix() for n in sorted(h)],
                 'ubuntu@192.168.2.2:' + REMOTE + '/'], log)
            verify(h, log)
        elif a.mode == 'readback':
            verify(h, log)
        else:
            out = LOCAL / 'board-result'
            out.mkdir()
            names = ['stage-result.jsonl', 'staged-module-hashes.json']
            output = run([SSH, '-T', *OPTIONS, 'ubuntu@192.168.2.2', GUARD +
                          'cd ' + REMOTE + '; sha256sum ' + ' '.join(names)], log)
            pins = {line.split()[1]:line.split()[0] for line in output.splitlines() if len(line.split()) == 2}
            run([SCP, *OPTIONS, *['ubuntu@192.168.2.2:' + REMOTE + '/' + n for n in names], str(out)], log)
            if set(pins) != set(names) or any(sha(out / n) != pins[n] for n in names):
                raise ValueError('Downloaded evidence hash mismatch')
            print('BOARD_RECEIPT_DOWNLOAD_HASH_MATCH')


if __name__ == '__main__':
    main()
