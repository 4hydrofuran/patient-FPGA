"""Create an independent private PC incremental kernel tree; never touches board.

Preserve the rejected source/build verbatim. Rewrite only cloned build metadata
paths and the separately tested ownership source, and assign a distinct release.
"""
import hashlib
import json
from pathlib import Path
import subprocess

OLD = Path('/home/member-a/a10-kernel-full-20261019-v1')
NEW = Path('/home/member-a/a10-kernel-irq2-20261021-v1')
PATCHED = Path('/mnt/c/Patientqwen/platform/build/a10-intc-data-owner-20261021-v1/candidate.c')


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def prepare():
    if NEW.exists():
        raise RuntimeError('Independent output already exists; never overwrite/restart')
    src = Path('drivers/irqchip/irq-xilinx-intc.c')
    if digest(OLD / 'source' / src) != '2306934f1a7ca152a4732b3a1f7807c1d20d54a3cfe5e5c3fad2a36f35d3252a':
        raise RuntimeError('old source changed')
    if digest(PATCHED) != '3e9b896dc046f2bbfa2208ff78f7fc0c136a98318e45f0cfe4ff90fcca8a4a07':
        raise RuntimeError('tested fix changed')
    NEW.mkdir(mode=0o700)
    report = dict(status='PREPARING_PC_ONLY', old=str(OLD), new=str(NEW), commands=[])
    with (NEW / 'prepare.json').open('x') as receipt:
        for name in ('source', 'build'):
            cmd = ['cp', '-a', '--reflink=auto', str(OLD / name), str(NEW / name)]
            p = subprocess.run(cmd, capture_output=True, text=True)
            report['commands'].append(dict(argv=cmd, exit_code=p.returncode, stderr=p.stderr))
            if p.returncode:
                raise RuntimeError('clone failed; preserve partial directory')
        # Bulk mechanical rewrite of cloned make dependency metadata only.
        rewritten = 0
        for p in (NEW / 'build').rglob('*.cmd'):
            raw = p.read_bytes()
            replacement = raw.replace(str(OLD).encode(), str(NEW).encode())
            if raw != replacement:
                p.write_bytes(replacement)
                rewritten += 1
        (NEW / 'source' / src).write_bytes(PATCHED.read_bytes())
        # Private read-only reuse of installed host tools, not a dependency upgrade.
        (NEW / 'deps').symlink_to(OLD / 'deps', target_is_directory=True)
        (NEW / 'logs').mkdir(mode=0o700)
        report.update(status='PC_CLONED_NOT_CONFIGURED_NOT_BOARD',
                      cloned_cmd_paths_rewritten=rewritten, candidate_source_sha256=digest(NEW / 'source' / src))
        json.dump(report, receipt, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != 'commands'}))


if __name__ == '__main__':
    prepare()
