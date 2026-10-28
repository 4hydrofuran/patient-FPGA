"""Receive only B's pinned web_gateway subtree; do not import B's compute repository."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import urllib.request
import time

REPO='4hydrofuran/patient-FPGA'
BRANCH='frontend/web-gateway-20261026'
HEAD='601e69ca2896aa9939c1d7e28220b35a59150260'
def request(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Codex-A-frontend-intake'}),timeout=40) as r:return r.read()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def receive(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=a.resume)
    head=json.loads(request(f'https://api.github.com/repos/{REPO}/commits/{BRANCH}'))
    assert head['sha']==HEAD,'upstream advanced; select the new commit explicitly before receiving'
    tree=json.loads(request(f'https://api.github.com/repos/{REPO}/git/trees/{HEAD}?recursive=1'))
    assert tree['truncated'] is False
    rows=[r for r in tree['tree'] if r['type']=='blob' and r['path'].startswith('web_gateway/')]
    def download(row):
        p=out/row['path']
        if p.is_file():data=p.read_bytes()
        else:
            existing=Path(__file__).resolve().parent/'vendor'/row['path']
            cached=existing.read_bytes() if existing.is_file() else b''
            if hashlib.sha1(b'blob '+str(len(cached)).encode()+b'\0'+cached).hexdigest()==row['sha']:data=cached
            else:
                import base64
                blob=json.loads(request(f'https://api.github.com/repos/{REPO}/git/blobs/'+row['sha']))
                assert blob['encoding']=='base64'
                data=base64.b64decode(blob['content'])
        assert len(data)==row['size']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==row['sha'],row['path']
        if not p.is_file():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        return dict(path=row['path'],bytes=len(data),git_blob_sha1=row['sha'],sha256=hashlib.sha256(data).hexdigest())
    with ThreadPoolExecutor(max_workers=6) as pool:files=list(pool.map(download,rows))
    receipt=dict(status='PASS_PINNED_B_FRONTEND_RECEIVED',provider='B',repository='https://github.com/'+REPO,
        branch=BRANCH,commit=HEAD,upstream_commit_at=head['commit']['committer']['date'],
        received_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),scope='web_gateway only; original received bytes retained',
        files=files,BOARD='NOT_TESTED')
    save(out/'INTAKE.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'}|{'file_count':len(files)},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--resume',action='store_true')
    receive(p.parse_args())
