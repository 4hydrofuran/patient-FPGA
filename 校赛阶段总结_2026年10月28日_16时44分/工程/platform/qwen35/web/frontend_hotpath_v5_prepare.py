"""Retain the v4 failure and fix startup/port handover before a fresh window."""
import base64,gzip,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'release/a12_board_hotpath_20261027_v4/b601e69ca-cache-profile-t4'
NEW=ROOT/'release/a12_board_hotpath_20261027_v5/b601e69ca-cache-profile-t4'
EV=ROOT/'evidence/frontend_board_A/20261027-b601e69ca-board-run-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copytree(OLD,NEW,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
p=NEW/'start_board.py';s=p.read_text(encoding='utf-8')
s=s.replace('first_actual_PL_web_answer=True,answer_cache=False', 'first_actual_PL_web_answer=True,answer_cache=True')
needle="    if target.exists():raise RuntimeError('window directory already exists; use a fresh name')"
assert s.count(needle)==1
s=s.replace(needle,needle+'''
    # A result-only server can outlive release. Detect port ownership BEFORE PL.
    import socket
    with socket.socket() as port:
        try:port.bind(('127.0.0.1',8000))
        except OSError as exc:raise RuntimeError('previous HTTP result view still owns port 8000; no new Owner started') from exc
''')
p.write_text(s,encoding='utf-8');changed=[p]
p=NEW/'continuous/interactive_case.py';s=p.read_text(encoding='utf-8')
needle="        raise RuntimeError('Web initialization failed')";assert s.count(needle)==1
s=s.replace(needle,"""        api.save(path/'WEB_START_FAILED.json',dict(status='WEB_START_FAILED_NO_QUESTION_ACCEPTED',
            reason='HTTP server did not start',normal_worker_drain_requested=True))
        # No question has been accepted. Return through the original platform
        # restore/finalization path after the ordinary worker shutdown completes.
        assert worker.close(timeout=30) and worker.closed and worker.process.returncode==0
        return transport.warm_result""")
s=s.replace('    if SERVER is not None:\n        time.sleep(seconds)', '    if SERVER is not None and SERVER.started:\n        time.sleep(seconds)')
p.write_text(s,encoding='utf-8');changed.append(p)
m=json.loads((NEW/'MANIFEST.json').read_text());m['profile_id']='b601e69ca-cache-profile-v5'
for row in m['files']:
    p=NEW/row['path']
    if p in changed:row.update(bytes=p.stat().st_size,sha256=sha(p))
save(NEW/'MANIFEST.json',m);changed.append(NEW/'MANIFEST.json')
files=[dict(path=p.relative_to(NEW).as_posix(),before_sha256=sha(OLD/p.relative_to(NEW)),after_sha256=sha(p),gzip_base64=base64.b64encode(gzip.compress(p.read_bytes(),mtime=0)).decode()) for p in changed]
payload='FILES='+repr(files)+'''
import base64,gzip,hashlib,json,shutil
from pathlib import Path
old=Path('/home/ubuntu/kv260-staging/a12-hotpath-20261027-v4/b601e69ca-cache-profile-t4')
new=Path('/home/ubuntu/kv260-staging/a12-hotpath-20261027-v5/b601e69ca-cache-profile-t4')
assert not new.exists()
for f in FILES:assert hashlib.sha256((old/f['path']).read_bytes()).hexdigest()==f['before_sha256']
shutil.copytree(old,new,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for f in FILES:
    data=gzip.decompress(base64.b64decode(f['gzip_base64']));assert hashlib.sha256(data).hexdigest()==f['after_sha256']
    (new/f['path']).write_bytes(data)
out={'status':'HOTPATH_V5_PORT_HANDOVER_FIX_STAGED','path':str(new)}
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(out),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
'''
(EV/'stage_hotpath_v5.py').write_text(payload,encoding='utf-8')
print(json.dumps({'candidate':str(NEW),'changed_files':len(files)}))
