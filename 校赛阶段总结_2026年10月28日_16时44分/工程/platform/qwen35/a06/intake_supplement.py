"""Receive only the user-requested B03 release, immutable SHA and safe extraction."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[3]
E = ROOT / 'evidence/A06_acceptance/supplement-v1'
D = ROOT / 'hw/linear_B_received/B03-supplement-e227297-20261003'
API = 'https://api.github.com/repos/4hydrofuran/patient-FPGA'
TAG = 'b03-a06-supplement-20261003'
sys.path.insert(0, str(ROOT / 'platform/qwen35/a07'))
from inspect_delivery import inspect, entries

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f: f.write(data)

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'A06-B03-receipt'})
    return urllib.request.urlopen(req, timeout=60)

def main():
    E.mkdir(parents=True, exist_ok=True)
    D.mkdir(parents=True, exist_ok=True)
    for name in ['docs/PROJECT_STATUS.json','docs/status/A.md','hw/linear_A/KERNEL_SOURCE.json',
                 'docs/DESIGN_GAP.md','docs/TEST_MATRIX.md']:
        dest = E / 'before' / name
        if not dest.exists(): save(dest, (ROOT/name).read_bytes())
    meta = E / 'release.json'
    if not meta.exists():
        with fetch(API+'/releases/tags/'+TAG) as response: save(meta,response.read())
    release = json.loads(meta.read_bytes())
    assert release['tag_name'] == TAG
    records=[]
    for a in release['assets']:
        if a['name'] not in ['B03_A06_acceptance.json','B03_A06_SUPPLEMENT.md',
                              'B03_A06_supplement_20261003.sha256.txt','B03_A06_supplement_20261003.zip']:
            continue
        path = D / a['name']
        if not path.exists():
            temp = D / (a['name']+'.download')
            if not temp.exists():
                with fetch(a['browser_download_url']) as response, temp.open('xb') as out:
                    shutil.copyfileobj(response,out,1024*1024)
            with temp.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
            if temp.stat().st_size!=a['size'] or 'sha256:'+actual!=a['digest']:
                raise RuntimeError('download digest mismatch')
            temp.rename(path)
        with path.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
        assert path.stat().st_size==a['size'] and 'sha256:'+actual==a['digest']
        records.append({'path':path.relative_to(ROOT).as_posix(),'sha256':actual,'bytes':a['size'],'url':a['browser_download_url']})
        print(json.dumps(records[-1]),flush=True)
    archive=D/'B03_A06_supplement_20261003.zip'
    inventory=inspect(archive,'506f079daabf37f6dc539d35c49add0b4c0e7629a0a97c461c470b0f75c59513')
    if not (E/'inventory.json').exists():save(E/'inventory.json',json.dumps(inventory,indent=2).encode())
    extracted=D/'payload'
    with zipfile.ZipFile(archive) as z:
        for info in entries(z):
            dest=extracted/info.filename
            if dest.exists():
                assert hashlib.sha256(dest.read_bytes()).hexdigest()==inventory['files'][info.filename]['sha256']
            else:save(dest,z.read(info))
    save(E/'download.json',json.dumps({'assets':records,'files':len(inventory['files']),'xo_count':len(inventory['xo']),
                                     'accepted':False,'BOARD':'NOT_TESTED'},indent=2).encode())
    print(json.dumps({'files':len(inventory['files']),'xo_count':len(inventory['xo']),'destination':str(extracted)}))

if __name__=='__main__':main()
