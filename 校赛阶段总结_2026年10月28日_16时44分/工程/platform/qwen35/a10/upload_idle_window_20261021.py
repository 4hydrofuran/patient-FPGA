"""Transfer the exact authorized idle window bundle; never execute it or install.

Default prints the exact plan. Credentials are requested only by OpenSSH's
terminal prompt; never passed through argv, environment or stored by this file.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from candidate_idle_trial import verify_bundle, validate_review, digest, need, MACHINE, KERNEL

ROOT = Path(__file__).resolve().parents[3]
E = ROOT / 'evidence/board_platform/A10_20261018_intake'
BUNDLE = ROOT / 'platform/local/a10-candidate-idle-20261021-v2'
REVIEW = E / 'idle-window-review-20261021-v1'
MANIFEST_SHA = '835624b36ce64a77c9a82f2f04bb23151073eb8bc6befcf6c892749d66279fb9'
REVIEW_SHA = '5624c85cbd83e43f18bc549b3275e7917a7171f35bbaca9cfad6066247f584dd'
BOOT = '751e617d-c003-4b99-be03-bb5c78235d24'
REMOTE = '/home/ubuntu/a10-idle-candidate-20261021-v2'
REMOTE_REVIEW = '/home/ubuntu/a10-idle-review-20261021-v1'


def commands(bundle=BUNDLE, manifest_sha=MANIFEST_SHA, remote=REMOTE, remote_review=REMOTE_REVIEW,
             reuse_review=False):
    allowed = {
        BUNDLE: REMOTE,
        BUNDLE.parent / 'a10-candidate-idle-20261021-v3':
            '/home/ubuntu/a10-candidate-idle-20261021-v3',
    }
    need(bundle in allowed, 'outside approved local bundle directory')
    need(remote == allowed[bundle] and
         remote_review == REMOTE_REVIEW, 'outside approved board user directories')
    manifest = verify_bundle(bundle, manifest_sha)
    need(digest(REVIEW / 'baseline.review.json') == REVIEW_SHA, 'review changed')
    raw = (REVIEW / 'baseline.raw.txt').read_bytes().decode()
    need(validate_review(json.loads((REVIEW / 'baseline.review.json').read_text()), raw)[0] == BOOT,
         'review boot changed')
    known = ROOT / 'platform/qwen35/a10/board_ssh_known_hosts'
    need(known.read_text().strip() ==
         '192.168.2.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe',
         'SSH host key pin changed')
    options = ['-o', 'BindAddress=192.168.2.1', '-o', f'UserKnownHostsFile={known.as_posix()}',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5',
               '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
               '-o', 'NumberOfPasswordPrompts=1', '-o', 'PubkeyAuthentication=no']
    guard = (
        f'set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = {BOOT}; '
        f'test "$(uname -r)" = {KERNEL}; test "$(id -u)" = 1000; '
        f'test "$(sha256sum /etc/machine-id | cut -d \' \' -f1)" = {MACHINE}; '
        'test ! -d /sys/module/zocl; test ! -e /var/lock/kv260-a1/active; '
        'test -d /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1; '
        'python3 -c "from pathlib import Path; t=[int(p.read_text()) for p in '
        'Path(\'/sys/class/hwmon\').glob(\'hwmon*/temp*_input\')]; print(t); '
        'assert t and all(0<x<55000 for x in t)"; '
        f'umask 077; mkdir {remote}; ' +
        (f'test -d {remote_review}' if reuse_review else f'mkdir {remote_review}'))
    files = [bundle / name for name in manifest['files']] + [bundle / 'bundle.pending.json']
    review_files = [REVIEW / 'baseline.raw.txt', REVIEW / 'baseline.review.json']
    hashes = {remote + '/' + p.name: digest(p)
              for remote, paths in ((remote, files), (remote_review, review_files)) for p in paths}
    readback = f'set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = {BOOT}; ' + '; '.join(
        f'test "$(sha256sum {shlex.quote(name)} | cut -d \' \' -f1)" = {sha}'
        for name, sha in hashes.items()) + '; printf "ALL_IDLE_UPLOAD_HASHES_MATCH\\n"'
    ssh = 'C:/Windows/System32/OpenSSH/ssh.exe'
    scp = 'C:/Windows/System32/OpenSSH/scp.exe'
    cmds = [
        [ssh, '-T', *options, 'ubuntu@192.168.2.2', guard],
        [scp, '-l', '32768', *options, *[str(p) for p in files], 'ubuntu@192.168.2.2:' + remote + '/']]
    if not reuse_review:
        cmds.append([scp, '-l', '32768', *options, *[str(p) for p in review_files],
                     'ubuntu@192.168.2.2:' + remote_review + '/'])
    cmds.append([ssh, '-T', *options, 'ubuntu@192.168.2.2', readback])
    return cmds, hashes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-authorized-upload', action='store_true')
    ap.add_argument('--receipt', type=Path)
    ap.add_argument('--raw-bytes-fixed-v3-manifest-sha256')
    args = ap.parse_args()
    if args.raw_bytes_fixed_v3_manifest_sha256:
        bundle = BUNDLE.parent / 'a10-candidate-idle-20261021-v3'
        cmds, hashes = commands(bundle, args.raw_bytes_fixed_v3_manifest_sha256,
                                '/home/ubuntu/' + bundle.name, reuse_review=True)
    else:
        cmds, hashes = commands()
    if not args.execute_authorized_upload:
        print(json.dumps(dict(board_contact=False, commands=cmds, hashes=hashes,
                              execute_on_board=False), indent=2))
        return 0
    need(args.receipt is not None, 'exclusive receipt required')
    report = dict(status='RESERVED_NOT_COMPLETED', boot_id=BOOT, commands=[], hashes=hashes,
                  pl_load=False, compute_runs=0)
    start = time.monotonic()
    with args.receipt.open('x', encoding='utf-8') as receipt:
        receipt.write(json.dumps(report)); receipt.flush()
        try:
            for command in cmds:
                # stderr/TTY retained for OpenSSH's real challenge. No password
                # is read, redirected, echoed or captured by this program.
                result = subprocess.run(command, stdout=subprocess.PIPE, text=True)
                report['commands'].append(dict(argv=command, exit_code=result.returncode,
                                               stdout=result.stdout))
                print(result.stdout, flush=True)
                need(result.returncode == 0, 'upload step failed; no retry/delete/execution')
            report['status'] = 'USER_DIRECTORY_UPLOAD_HASH_VERIFIED_NOT_EXECUTED'
        except Exception as exc:
            report['error'] = str(exc)
            report['status'] = 'STOPPED_NO_AUTOMATIC_RETRY'
        finally:
            report['elapsed_s'] = time.monotonic() - start
            receipt.seek(0); json.dump(report, receipt, indent=2); receipt.truncate()
    print(json.dumps(dict(status=report['status'], receipt=str(args.receipt)), indent=2))
    return 0 if report['status'] == 'USER_DIRECTORY_UPLOAD_HASH_VERIFIED_NOT_EXECUTED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
