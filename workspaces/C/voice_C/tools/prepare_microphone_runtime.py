"""Create a separate local microphone runtime from the existing locked wheels.

Never changes .venv, global packages, historical installation logs or drivers.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / '.venv_mic'
    if target.exists():
        raise RuntimeError('Microphone runtime already exists; refusing to overwrite')
    wheels = ROOT / 'assets/wheels'
    rows = json.loads((wheels / 'wheels.lock.json').read_text(encoding='utf-8'))
    for row in rows:
        if hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Locked wheel hash mismatch')
    base = Path(sys.base_prefix) / 'python.exe'
    commands = [
        [str(base), '-m', 'venv', '--without-pip', str(target)],
        [str(base), '-m', 'pip', 'install', '--disable-pip-version-check', '--no-index',
         '--find-links', str(wheels), '--require-hashes', '--no-compile',
         '--target', str(target / 'Lib/site-packages'), '-r', str(ROOT / 'requirements-c01.lock.txt')],
        [str(target / 'Scripts/python.exe'), '-c',
         "import importlib.metadata as m; import numpy,sherpa_onnx; print({k:m.version(k) for k in ('numpy','sherpa-onnx','sherpa-onnx-core')})"],
    ]
    evidence = ROOT / 'evidence/c03_mic'
    evidence.mkdir(exist_ok=True)
    results = []
    for command in commands:
        proc = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
            timeout=120, env=os.environ | dict(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1'))
        results.append(dict(argv=command, exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr))
        (evidence / 'microphone_runtime_install.json').write_text(json.dumps(dict(
            target=str(target), wheels=rows, network=False, original_venv_modified=False,
            commands=results), ensure_ascii=False, indent=2), encoding='utf-8')
        print(proc.stdout + proc.stderr, flush=True)
        if proc.returncode:
            return proc.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
