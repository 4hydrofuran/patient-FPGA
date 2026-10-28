"""Incremental retry; accept Windows manifest separators, not changed bytes."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path('/mnt/c/Patientqwen')
E = ROOT / 'evidence/A06_acceptance'
sys.path.insert(0, str(ROOT / 'platform/a1'))
from record import run

def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    raw = json.loads((E / 'test-inputs.sha256.json').read_text())
    snapshot = {k.replace('\\', '/'): v for k, v in raw.items()}
    if len(snapshot) != len(raw):
        raise RuntimeError('ambiguous normalized input paths')
    for name, expected in snapshot.items():
        if sha(ROOT / name) != expected:
            raise RuntimeError('changed test input: ' + name)
    received = json.loads((E / 'intake-v1/download-manifest.json').read_text())
    for f in received['files']:
        p = ROOT / 'hw/linear_B_received/B03-fdd1d656290b-20261003' / f['path']
        if sha(p) != f['sha256']:
            raise RuntimeError('received B file changed: ' + f['path'])
    out = E / 'csim-retry-rehost-20261003-v2'
    out.mkdir(exist_ok=False)
    results = []
    for variant in ['baseline', 'reuse', 'double']:
        cfg = Path.cwd() / (variant + '.cfg')
        cfg.write_bytes((E / f'local-tests-v1/{variant}.cfg').read_bytes())
        code = run(['/home/member-a/AMDDesignTools/2026.1/Vitis/bin/vitis-run',
                    '--mode', 'hls', '--csim', '--config', str(cfg),
                    '--work_dir', str(Path.cwd() / (variant + '-csim'))], out / (variant + '.json'))
        results.append({'variant': variant, 'exit_code': code})
        if code:
            break
    (out / 'summary.json').write_text(json.dumps(results, indent=2))
    return int(len(results) != 3 or any(v['exit_code'] for v in results))

if __name__ == '__main__':
    raise SystemExit(main())
