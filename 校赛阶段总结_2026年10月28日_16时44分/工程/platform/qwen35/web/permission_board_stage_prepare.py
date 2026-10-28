"""Make a small pinned delta against the already-staged twenty-case parent."""
import base64,gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PACK=ROOT/'release/a12_permission_scheduler_noboard_20261027_v2'
PARENT=ROOT/'release/a12_case20_random_board_20261027_v1/case20-random-t4'
EV=ROOT/'evidence/model_pl_A/20261027-permission-scheduler-board-v1';EV.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
data={};variants=[]
for name in ('baseline-miss-probe','candidate-miss-probe'):
    target=PACK/name;changes=[]
    for p in sorted(target.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        rel=p.relative_to(target).as_posix()
        if rel in ('MANIFEST.json','continuous/bundle/manifest.json'):continue
        before=PARENT/rel
        if not before.exists() or sha(before)!=sha(p):
            key=sha(p);data[key]=base64.b64encode(gzip.compress(p.read_bytes(),mtime=0)).decode()
            changes.append(dict(path=rel,sha256=key))
    variants.append(dict(name=name,changes=changes,manifest_sha256=sha(target/'MANIFEST.json'),
        bundle_manifest_sha256=sha(target/'continuous/bundle/manifest.json')))
plan=dict(parent_manifest_sha256=sha(PARENT/'MANIFEST.json'),variants=variants,contents=data)
receiver='PLAN='+repr(plan)+'''
import base64,gzip,hashlib,json,shutil,traceback
from pathlib import Path
source=Path('/home/ubuntu/kv260-staging/a12-case20-random-20261027-v1/case20-random-t4')
target=Path('/home/ubuntu/kv260-staging/a12-permission-scheduler-20261027-v1')
receipt=Path('/var/lib/kv260-a12/permission-scheduler-20261027-v1/STAGED.json')
out={'status':'STAGING','compute_runs':0,'pl_loads':0}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def refresh(root,name):
    path=root/name;value=json.loads(path.read_text())
    files=sorted((p for p in root.rglob('*') if p.is_file() and p!=path and '__pycache__' not in p.parts),
        key=lambda p:tuple(x.lower() for x in p.relative_to(root).parts))
    value['files']=[dict(path=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\\n')
try:
    assert sha(source/'MANIFEST.json')==PLAN['parent_manifest_sha256'] and not target.exists()
    target.mkdir(parents=True)
    out['variants']=[]
    for v in PLAN['variants']:
        root=target/v['name'];shutil.copytree(source,root,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for f in v['changes']:
            rel=Path(f['path']);assert not rel.is_absolute() and '..' not in rel.parts
            payload=gzip.decompress(base64.b64decode(PLAN['contents'][f['sha256']]))
            assert hashlib.sha256(payload).hexdigest()==f['sha256']
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(payload)
        refresh(root/'continuous/bundle','manifest.json');refresh(root,'MANIFEST.json')
        assert sha(root/'MANIFEST.json')==v['manifest_sha256'],v['name']+' root manifest differs'
        assert sha(root/'continuous/bundle/manifest.json')==v['bundle_manifest_sha256']
        out['variants'].append(dict(name=v['name'],manifest_sha256=v['manifest_sha256']))
    out.update(status='PINNED_COMPARISON_CANDIDATES_STAGED',root=str(target))
except Exception as e:out.update(status='FAILED_PRESERVE_PARTIAL_STATE',error=type(e).__name__+': '+str(e),traceback=traceback.format_exc())
receipt.write_text(json.dumps(out,indent=2)+'\\n')
'''
payload='RECEIVER='+repr(receiver)+'''
import hashlib,json,os,subprocess
from pathlib import Path
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='98886b24-96d3-409e-a783-ce9c54873da9'
root=Path('/var/lib/kv260-a12/permission-scheduler-20261027-v1');root.mkdir(exist_ok=False)
p=root/'stage_receiver.py';p.write_text(RECEIVER)
with (root/'stage.stdout').open('xb') as out,(root/'stage.stderr').open('xb') as err:
    process=subprocess.Popen(['/usr/bin/python3','-B',str(p)],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
r=dict(status='STAGING_DETACHED',pid=process.pid,root=str(root),current_service_changed=False)
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(r),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
'''
(ROOT/'evidence/frontend_board_A/20261027-b601e69ca-board-run-v1/permission_stage_board.py').write_text(payload,encoding='utf-8')
(EV/'STAGE_PLAN.json').write_text(json.dumps({k:v for k,v in plan.items() if k!='contents'},indent=2)+'\n')
print(json.dumps(dict(changed_content_blobs=len(data),payload_bytes=len(payload.encode()))))
