"""Verify an unchanged baseline handoff; stdlib only, never touches devices."""
import hashlib
import json
from pathlib import Path
import re
import sys

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    expected = manifest['files']
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(expected) | {'MANIFEST.json'}:
        raise ValueError('Unexpected or missing files; keep work/build/output outside package')
    total = 0
    banned = {'.gguf', '.safetensors', '.xclbin', '.xo', '.bit', '.pdi', '.vhdx', '.whl', '.so', '.exe'}
    for name, meta in expected.items():
        path = root / name
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError('Unsafe path')
        if path.suffix.lower() in banned or any(x in {'.git', '.ssh', '.env', '__pycache__'} for x in path.parts):
            raise ValueError('Excluded artifact type: ' + name)
        data = path.read_bytes()
        if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
            raise ValueError('Hash/length mismatch: ' + name)
        if re.search(rb'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----', data):
            raise ValueError('Private key content rejected')
        if re.search(rb'(?i)(?:password|passwd|api_key|access_token)\s*[:=]\s*[\x22\x27][^\x22\x27\r\n]{6,}[\x22\x27]', data):
            raise ValueError('Potential credential assignment: ' + name)
        total += len(data)
    if total > 60 * 1024 * 1024:
        raise ValueError('Package exceeded source-only budget')
    return {'status': 'PASS_PACKAGE_INTEGRITY_AND_EXCLUSION_SCAN', 'files': len(expected),
            'bytes': total, 'BOARD': 'NOT_TESTED', 'scope': 'STATIC_PACKAGE_ONLY'}

if __name__ == '__main__':
    try:
        print(json.dumps(verify(Path(__file__).resolve().parents[1]), indent=2))
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)})); sys.exit(1)
