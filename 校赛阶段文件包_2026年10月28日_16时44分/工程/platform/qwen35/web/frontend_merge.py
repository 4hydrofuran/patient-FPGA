"""Three-way merge B's seven frontend changes onto A's tested host integration."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
BASE='40498c2388b6293d68f38907c71ffd8933a5803e'
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Codex-A-frontend-merge'}),timeout=15) as r:return json.load(r)
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def merge(a):
    received=a.received.resolve();intake=json.loads((received/'INTAKE.json').read_text(encoding='utf-8'))
    assert intake['status']=='PASS_PINNED_B_FRONTEND_RECEIVED'
    changes=json.loads((a.evidence/'UPSTREAM_CHANGE.json').read_text(encoding='utf-8'))
    entries=[r for r in changes['files'] if r['filename'].startswith('web_gateway/src/')]
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    gateway=out/'web_gateway';shutil.copytree(HERE/'vendor/web_gateway',gateway,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    tree=fetch(f'https://api.github.com/repos/4hydrofuran/patient-FPGA/git/trees/{BASE}?recursive=1')
    blobs={r['path']:r['sha'] for r in tree['tree'] if r['type']=='blob'}
    base_root=out/'merge-base404';base_root.mkdir()
    def download_base(row):
        relative=row['filename']
        if row['status']=='added':return
        cached=a.base_cache/relative if a.base_cache else None
        if cached and cached.is_file():data=cached.read_bytes()
        else:
            original=fetch('https://api.github.com/repos/4hydrofuran/patient-FPGA/git/blobs/'+blobs[relative])
            data=base64.b64decode(original['content'])
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[relative]
        target=base_root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(download_base,entries))
    results=[]
    for row in entries:
        relative=row['filename'];target=out/relative;source=received/relative
        if row['status']=='added':shutil.copyfile(source,target);code=0
        else:
            r=subprocess.run(['git','merge-file','-p','--diff3',str(target),str(base_root/relative),str(source)],capture_output=True)
            if r.returncode<0 or r.returncode>=128:raise RuntimeError(r.stderr.decode())
            target.write_bytes(r.stdout);code=r.returncode
        results.append(dict(path=relative,status='CONFLICT_REQUIRES_A_RESOLUTION' if code else 'MERGED',sha256=sha(target)))
    for row in changes['files']:
        if row['filename'].startswith('web_gateway/tests/'):
            target=out/row['filename'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(received/row['filename'],target)
    save(out/'MERGE.json',dict(provider='B',maintainer='A',upstream_commit=intake['commit'],base_commit=BASE,
        A_baseline='a12_realtime_tail_20261027_1446_BJT_v2',files=results,BOARD='NOT_TESTED'))
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--received',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--base-cache',type=Path);merge(p.parse_args())
