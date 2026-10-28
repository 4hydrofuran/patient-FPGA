"""Final independent-scope integrity seal; never certifies a B kernel or board."""
import datetime,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
E=ROOT/'evidence/A07_independent/preboard-v1'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text())
def new(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)

assert read(E/'finalize-v2.json')['exit_code']==0
for name in ('contracts-final.json','config-final.json','queue-final.json'):
    assert read(E/name)['exit_code']==0,name
queue=json.loads(read(E/'queue-final.json')['stdout']);assert queue['active'] is None and not queue['pending']
old=read(ROOT/'evidence/A06_acceptance/intake-v1/download-manifest.json')
received=ROOT/'hw/linear_B_received/B03-fdd1d656290b-20261003'
for item in old['files']:assert sha(received/item['path'])==item['sha256'],item['path']
package=ROOT/'platform/build/a07-independent-a53-v2'
for name,item in read(package/'manifest.json')['files'].items():assert sha(package/name)==item['sha256'],name
files={}
exclude={'files.sha256.json','SEAL.json','seal-command.json'}
for directory in (E,ROOT/'platform/qwen35/a07',ROOT/'modules/linear_A/xrt',package):
    for p in directory.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and not (p.parent==E and p.name in exclude):
            files[p.relative_to(ROOT).as_posix()]=sha(p)
for name in ('docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md',
             'docs/AI_ASSISTANCE.md','docs/handoffs/A_A07_INDEPENDENT_20261003.md'):
    files[name]=sha(ROOT/name)
new(E/'files.sha256.json',files)
new(E/'SEAL.json',{'status':'PASS_INTEGRITY_ONLY','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'files':len(files),'inventory_sha256':sha(E/'files.sha256.json'),'B_received_files_unchanged':len(old['files']),
    'queue_empty':True,'A06_accepted':False,'BOARD':'NOT_TESTED',
    'excluded_self_envelopes':sorted(exclude),'new_commit':None,'pushed':False})
print(json.dumps(read(E/'SEAL.json')))
