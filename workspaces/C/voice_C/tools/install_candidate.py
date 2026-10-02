"""Install into a new runtime directory using only hash-locked offline wheels."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-runtime',type=Path,required=True)
    args=parser.parse_args(); target=args.target_runtime.resolve()
    if sys.version_info[:2] != (3,12) or platform.python_implementation() != 'CPython':
        parser.error('Pinned wheels require CPython 3.12; do not change global Python to install this package')
    if os.name=='nt' and platform.machine().lower() in ('amd64','x86_64'):
        wheel_dir=ROOT/'assets/wheels'; requirement=ROOT/'requirements-c01.lock.txt'
    elif sys.platform=='linux' and platform.machine().lower() in ('aarch64','arm64'):
        if platform.libc_ver()[0] != 'glibc' or tuple(map(int,platform.libc_ver()[1].split('.')[:2])) < (2,27):
            parser.error('This prepared ARM wheel set requires GNU/Linux glibc >=2.27; actual A53 compatibility remains untested')
        wheel_dir=ROOT/'assets/arm/wheels'; requirement=ROOT/'assets/arm/requirements-aarch64.lock.txt'
    else: parser.error('No pinned offline wheel set for this OS/architecture')
    for row in json.loads((wheel_dir/'wheels.lock.json').read_text('utf-8')):
        path=ROOT/row['path']
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink(): raise ValueError('Unsafe wheel lock path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Locked wheel hash mismatch')
    if target==ROOT or target.is_relative_to(ROOT):parser.error('Install to a new directory outside the sealed package')
    if target.exists():parser.error('Target must be new; existing directories are never overwritten')
    # Check file integrity before installing or executing the copied module.
    if (ROOT/'manifest.json').exists():
        sys.path.insert(0,str(ROOT/'tools'))
        from verify_bundle import check_bundle
        check_bundle(ROOT,ROOT/'contracts/contract_lock.json')
    target.mkdir(parents=True)
    for name in ('voicec','bin','tests','configs','contracts'):
        shutil.copytree(ROOT/name,target/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (target/'assets/asr').mkdir(parents=True);(target/'assets/tts').mkdir(parents=True)
    for name in ('asr','tts'):
        shutil.copyfile(ROOT/f'assets/{name}/model.lock.json',target/f'assets/{name}/model.lock.json')
    shutil.copytree(ROOT/'data',target/'data')
    (target/'tools').mkdir()
    for name in ('stream_c03_microphone.py','run_microphone.ps1','materialize_local_assets.py'):
        shutil.copyfile(ROOT/'tools'/name,target/'tools'/name)
    base=Path(sys._base_executable)
    commands=[
        [str(base),'-m','venv',str(target/'.venv')],
        [str(target/'.venv/Scripts/python.exe' if os.name=='nt' else target/'.venv/bin/python'),'-m','pip','install',
         '--disable-pip-version-check','--no-index','--find-links',str(wheel_dir),'--require-hashes','--no-compile','-r',str(requirement)]]
    history=[]
    for cmd in commands:
        proc=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=120,
            env=os.environ|dict(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1'))
        history.append(dict(argv=cmd,exit_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
        (target/'installation.json').write_text(json.dumps(dict(source=str(ROOT),target=str(target),
            network=False,global_environment_modified=False,commands=history),indent=2)+'\n',encoding='utf-8')
        print(proc.stdout+proc.stderr,flush=True)
        if proc.returncode:return proc.returncode
    print('Isolated offline runtime installed; model assets omitted until locally supplied and hash-checked.')
    return 0


if __name__=='__main__':raise SystemExit(main())
