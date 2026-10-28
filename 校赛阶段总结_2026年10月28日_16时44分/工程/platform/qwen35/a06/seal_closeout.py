"""Seal A closeout files and revalidate received originals; no credentials."""
import hashlib
import json
from pathlib import Path
R = Path(__file__).resolve().parents[3]
E = R / 'evidence/A06_acceptance/a-owned-closeout-v1'


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def main():
    files = {}
    paths = list(E.rglob('*')) + list((R / 'platform/qwen35/a06').glob('*.py'))
    paths += list((R / 'platform/qwen35/a06').glob('*.sh'))
    paths += [R / n for n in ['AGENTS.md', 'docs/PROJECT_STATUS.json', 'docs/status/A.md',
              'docs/DESIGN_GAP.md', 'docs/TEST_MATRIX.md', 'docs/handoffs/A_A06_OWNED_CLOSEOUT_20261003.md']]
    paths += list((R / 'hw/linear_A').glob('*'))
    for p in paths:
        if not p.is_file() or p.name in ['seal-v2.json', 'files.sha256.json'] or '__pycache__' in p.parts:
            continue
        if p.suffix == '.lic':
            raise RuntimeError('License cannot enter evidence seal')
        files[p.relative_to(R).as_posix()] = sha(p)
    original = R / 'hw/linear_B_received/B03-supplement-e227297-20261003'
    manifest = json.loads((original / 'payload/B03_package_manifest.json').read_text(encoding='utf-8'))
    for name, entry in manifest['files'].items():
        p = original / 'payload' / name
        digest = sha(p)
        assert digest == entry['sha256'], name
        files[p.relative_to(R).as_posix()] = digest
    for p in [original / 'B03_A06_supplement_20261003.zip',
              original / 'payload/B03_package_manifest.json', original / 'payload/B03_supplement_manifest.json']:
        files[p.relative_to(R).as_posix()] = sha(p)
    status = json.loads((R / 'docs/PROJECT_STATUS.json').read_text(encoding='utf-8'))
    kernel = json.loads((R / 'hw/linear_A/KERNEL_SOURCE.json').read_text(encoding='utf-8'))
    report = json.loads((E / 'REPORT.json').read_text(encoding='utf-8'))
    assert status['stage_status'] == report['status']
    assert not status['a06_awaiting_B'] and not kernel['accepted'] and not kernel['frozen']
    assert kernel['xo_sha256'] == report['xo_sha256']
    assert report['vectors_exact_sha'] == 382
    path = E / 'files.sha256.json'
    with path.open('x', encoding='utf-8') as f:
        json.dump({'scope': 'A06_A_OWNED_TOOLING_COMPLETE_LOCAL_CSIM_BLOCKED',
                   'files': dict(sorted(files.items())), 'new_commit': None,
                   'excludes': ['self', 'commands/seal-v2.json (in flight)', 'licenses']}, f, indent=2)
    for name, digest in files.items():
        assert sha(R / name) == digest, name
    print(json.dumps({'status': 'PASS_INCREMENTAL_SEAL_NOT_A06_PASS', 'files': len(files),
                      'sha256': sha(path)}))


if __name__ == '__main__':
    main()
