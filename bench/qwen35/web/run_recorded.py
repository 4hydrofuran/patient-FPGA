"""Run one explicit command and preserve stdout/stderr, exit code and log hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    if a.command[:1]==['--']:a.command=a.command[1:]
    a.output.mkdir(parents=True,exist_ok=False)
    begin=time.monotonic()
    with (a.output/'stdout.txt').open('wb') as stdout,(a.output/'stderr.txt').open('wb') as stderr:
        r=subprocess.run(a.command,stdout=stdout,stderr=stderr)
    receipt=dict(command=a.command,cwd=str(Path.cwd()),exit_code=r.returncode,elapsed_s=time.monotonic()-begin,
        logs={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in a.output.glob('*.txt')})
    (a.output/'COMMAND.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2));raise SystemExit(r.returncode)
