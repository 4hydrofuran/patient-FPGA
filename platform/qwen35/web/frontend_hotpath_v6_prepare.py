"""Finalize the tested port handover in a fresh staged performance candidate."""
import base64,gzip,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'release/a12_board_hotpath_20261027_v5/b601e69ca-cache-profile-t4'
NEW=ROOT/'release/a12_board_hotpath_20261027_v6/b601e69ca-verified-cache-t4'
EV=ROOT/'evidence/frontend_board_A/20261027-b601e69ca-board-run-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
shutil.copytree(OLD,NEW,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copyfile(Path(__file__).with_name('frontend_start_board.py'),NEW/'start_board.py')
changed=[NEW/'start_board.py']
m=json.loads((NEW/'MANIFEST.json').read_text());m['profile_id']='b601e69ca-verified-cache-hotpath-v6'
for row in m['files']:
    p=NEW/row['path']
    if p in changed:row.update(bytes=p.stat().st_size,sha256=sha(p))
(NEW/'MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');changed.append(NEW/'MANIFEST.json')
files=[dict(path=p.relative_to(NEW).as_posix(),before_sha256=sha(OLD/p.relative_to(NEW)),after_sha256=sha(p),gzip_base64=base64.b64encode(gzip.compress(p.read_bytes(),mtime=0)).decode()) for p in changed]
payload='FILES='+repr(files)+'''
import base64,gzip,hashlib,json,shutil
from pathlib import Path
old=Path('/home/ubuntu/kv260-staging/a12-hotpath-20261027-v5/b601e69ca-cache-profile-t4')
new=Path('/home/ubuntu/kv260-staging/a12-hotpath-20261027-v6/b601e69ca-verified-cache-t4')
assert not new.exists()
for f in FILES:assert hashlib.sha256((old/f['path']).read_bytes()).hexdigest()==f['before_sha256']
shutil.copytree(old,new,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for f in FILES:
    data=gzip.decompress(base64.b64decode(f['gzip_base64']));assert hashlib.sha256(data).hexdigest()==f['after_sha256']
    (new/f['path']).write_bytes(data)
out={'status':'HOTPATH_V6_STAGED','path':str(new)}
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(out),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
'''
(EV/'stage_hotpath_v6.py').write_text(payload,encoding='utf-8')
print(json.dumps({'candidate':str(NEW),'changed_files':len(files)}))
