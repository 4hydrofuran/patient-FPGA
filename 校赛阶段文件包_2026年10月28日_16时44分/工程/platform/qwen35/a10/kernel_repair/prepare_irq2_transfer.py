"""PC-only pinned transfer directory and real-archive extraction rehearsal."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stage_irq2_board as irq2
import stage_candidate_board as base

ROOT = Path('/mnt/c/Patientqwen')
WORK = Path('/home/member-a/a10-kernel-irq2-20261021-v1')
OUT = ROOT / 'platform/local/a10-irq2-transfer-20261021-v1'
TOOLS = Path(__file__).parent


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def main():
    if os.uname().machine != 'x86_64':
        raise ValueError('PC only')
    receipt = json.loads((ROOT / 'evidence/board_platform/A10_20261018_intake/irq2_package_20261021_01.json').read_text())
    if receipt['exit_code'] != 0:
        raise ValueError('Completed packaging required')
    proof = ROOT / 'platform/local/a10-candidate-transfer-20261020-v1/original-backup-proof.json'
    if digest(proof) != irq2.PROOF_SHA:
        raise ValueError('Original proof changed')
    archive = ROOT / 'platform/local/a10-boot-backup-20261020/modules-v1/original-modules.tar'
    original = json.loads(proof.read_text())
    if archive.stat().st_size != original['archive_bytes'] or digest(archive) != original['archive_sha256']:
        raise ValueError('Verified original backup no longer present/matching')
    irq2.configure()
    for name, (size, sha) in irq2.PINNED.items():
        p = WORK / 'boot-candidate-v2' / name
        if p.stat().st_size != size or digest(p) != sha:
            raise ValueError('Candidate package changed')
    result = base.unpack_modules(WORK / 'boot-candidate-v2/modules.tar.gz',
                                WORK / 'irq2-extraction-rehearsal-v1', base.Limiter(rate=10**10))
    if base.digest(WORK / 'irq2-extraction-rehearsal-v1/extra/zocl.ko') != base.ZOCL_SHA:
        raise ValueError('Extracted driver differs')
    OUT.mkdir(mode=0o700)
    sources = {name: WORK / 'boot-candidate-v2' / name for name in irq2.PINNED}
    sources.update({name: TOOLS / name for name in
                    ('stage_irq2_board.py', 'stage_candidate_board.py', 'original_module_backup.py')})
    sources['original-backup-proof.json'] = proof
    hashes = {}
    for name, p in sources.items():
        with p.open('rb') as src, (OUT / name).open('xb') as dst:
            shutil.copyfileobj(src, dst, 1024**2)
        hashes[name] = digest(OUT / name)
        if hashes[name] != digest(p):
            raise ValueError('Transfer copy mismatch')
    manifest = dict(status='PC_PREPARED_NOT_UPLOADED', board_access=False, hashes=hashes,
                    plan=irq2.plan(), rehearsal={k:v for k,v in result.items() if k != 'readback_sha256'})
    with (OUT / 'manifest.json').open('x') as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
