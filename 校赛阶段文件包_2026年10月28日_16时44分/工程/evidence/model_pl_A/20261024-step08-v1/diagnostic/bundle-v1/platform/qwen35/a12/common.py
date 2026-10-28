"""A12 local evidence helpers; no implicit hardware or network operations."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'evidence/model_pl_A/20261023-preboard-v1'
CONTRACT = '83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def command(argv, log, cwd=ROOT, env=None):
    start = time.monotonic()
    # Reserve the receipt before executing; never overwrite a failed attempt.
    log = Path(log)
    save(log, dict(status='RUNNING', argv=list(map(str, argv)), cwd=str(cwd)))
    result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    row = dict(argv=list(map(str, argv)), cwd=str(cwd), exit_code=result.returncode,
               elapsed_s=time.monotonic()-start, stdout=result.stdout, stderr=result.stderr)
    log.write_text(json.dumps(row, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'command exit {result.returncode}; see {log}')
    return result
