"""A12 pinned SSH reviewed-script transport, authentication only at hidden prompts."""
import argparse
import base64
import getpass
import gzip
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from fetch_single_result import plan,PROMPT


def main():
    p=argparse.ArgumentParser();p.add_argument('--script',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();code=a.script.read_bytes();pin=hashlib.sha256(code).hexdigest()
    blob=base64.b64encode(gzip.compress(code)).decode();argv,_=plan()
    argv[-1]='sudo -S -p '+PROMPT.decode()+' /usr/bin/python3 -B -I -c "import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode(\''+blob+'\')); assert hashlib.sha256(b).hexdigest()==\''+pin+'\'; exec(compile(b,\'a12_step07_reviewed\',\'exec\'))"'
    a.output.mkdir(exist_ok=False,parents=True)
    (a.output/'reservation.json').write_text(json.dumps(dict(argv=argv,script_sha256=pin,scope='A12_STEP07_L00_MLP_AUTHORIZED'),indent=2))
    with (a.output/'stdout.txt').open('xb') as stream:
        proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.PIPE)
        q=queue.Queue()
        def read():
            for c in iter(lambda:proc.stderr.read(1),b''):q.put(c)
            q.put(b'')
        threading.Thread(target=read,daemon=True).start();err=bytearray();answered=False
        while True:
            try:c=q.get(timeout=20)
            except queue.Empty:print('Remote still running; no signal or retry.',flush=True);continue
            if not c:break
            err.extend(c)
            if err.endswith(PROMPT):
                if answered:raise RuntimeError('Repeated authentication challenge')
                secret=getpass.getpass('Verified board sudo; hidden credential: ')
                proc.stdin.write(secret.encode()+b'\n');proc.stdin.flush();secret=None;answered=True
        rc=proc.wait();proc.stdin.close()
    (a.output/'receipt.json').write_text(json.dumps(dict(exit_code=rc,stderr=err.decode(errors='replace'),script_sha256=pin),indent=2))
    print(json.dumps(dict(exit_code=rc,output=str(a.output))),flush=True);return rc


if __name__=='__main__':raise SystemExit(main())
