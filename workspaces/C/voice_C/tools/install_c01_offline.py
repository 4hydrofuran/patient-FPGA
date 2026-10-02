"""Reproducible hash-checked installation into the C voice venv only."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    wheels=ROOT/'assets/wheels'
    for row in json.loads((wheels/'wheels.lock.json').read_text()):
        path=ROOT/row['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Wheel hash mismatch')
    base=Path(r'C:\Users\quq\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
    target=ROOT/'.venv/Lib/site-packages'
    command=[str(base),'-m','pip','install','--disable-pip-version-check','--no-index',
        '--find-links',str(wheels),'--require-hashes','--target',str(target),
        '-r',str(ROOT/'requirements-c01.lock.txt')]
    # No global installation; no upgrade/force-reinstall of existing packages.
    proc=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=120,
        env=os.environ|{'PYTHONUTF8':'1'})
    evidence=ROOT/'evidence/c01'
    (evidence/'hash_checked_offline_install.log').write_text(proc.stdout+proc.stderr,encoding='utf-8')
    (evidence/'hash_checked_offline_install_command.json').write_text(json.dumps(dict(argv=command,exit_code=proc.returncode),indent=2)+'\n',encoding='utf-8')
    print('Hash-checked offline installation exit:',proc.returncode)
    raise SystemExit(proc.returncode)


if __name__=='__main__': main()
