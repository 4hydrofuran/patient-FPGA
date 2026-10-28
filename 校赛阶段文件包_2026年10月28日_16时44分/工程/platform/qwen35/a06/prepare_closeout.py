"""Verify the prior seal and save governance before the A-owned closeout edit."""
import hashlib
import json
from pathlib import Path
import shutil
R = Path(__file__).resolve().parents[3]
E = R / 'evidence/A06_acceptance/a-owned-closeout-v1'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def main():
    seal = R / 'evidence/A06_acceptance/supplement-v1/files.sha256.json'
    entries = json.loads(seal.read_text())['files']
    for name, digest in entries.items():
        if sha(R / name) != digest:
            raise ValueError('Prior sealed file changed: ' + name)
    out = E / 'before'; out.mkdir(exist_ok=False)
    copied = {}
    for name in ['AGENTS.md', 'docs/PROJECT_STATUS.json', 'docs/status/A.md',
                 'docs/DESIGN_GAP.md', 'docs/TEST_MATRIX.md', 'hw/linear_A/KERNEL_SOURCE.json']:
        target = out / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(R / name, target)
        copied[name] = sha(target)
    result = {'status': 'PASS', 'previous_seal_sha256': sha(seal),
              'verified_files': len(entries), 'governance_backup_hashes': copied}
    with (E / 'prior-integrity.json').open('x') as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
