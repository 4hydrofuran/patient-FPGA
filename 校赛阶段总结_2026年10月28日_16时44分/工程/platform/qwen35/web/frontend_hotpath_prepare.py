"""Prepare an isolated performance candidate from the deployed three-case frontend."""
import base64,gzip,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'release/a12_b_frontend_boardrun_20261027_v3/b601e69ca-realtime34-43-t4'
NEW=ROOT/'release/a12_board_hotpath_20261027_v4/b601e69ca-cache-profile-t4'
EV=ROOT/'evidence/frontend_board_A/20261027-b601e69ca-board-run-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copytree(OLD,NEW,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
changed=[]
for kind in ('ordinary','continuous'):
    w=NEW/kind
    if kind=='continuous':
        p=w/'web-config.json';c=json.loads(p.read_text(encoding='utf-8'))
        original=ROOT/'release/a12_realtime_tail_20261027_1446_BJT_v2/dual-neutral34-43-t4-out32'/kind/'web-config.json'
        c['answer_cache']=json.loads(original.read_text(encoding='utf-8'))['answer_cache']
        c['browser_profile']='/home/ubuntu/snap/firefox/common/a12-hotpath-v4-20261027'
        c['profile_model_requests']=True
        save(p,c);changed.append(p)
        p=w/'interactive_case.py';s=p.read_text(encoding='utf-8')
        s=s.replace('profile=False, diagnostic_report=False)',"profile=self.profile.get('profile_model_requests',False), diagnostic_report=False)")
        s=s.replace("profile=load_profile(overlay/config['profile']) if config.get('profile') else dict(LEGACY)","profile=load_profile(overlay/config['profile']) if config.get('profile') else dict(LEGACY)\n    profile['profile_model_requests']=config.get('profile_model_requests',False)")
        s=s.replace('prompt_builder=builder(profile),answer_cache=answer_cache)',"prompt_builder=builder(profile),answer_cache=None if config.get('verify_first') else answer_cache)")
        needle='        verify_first(worker,owner,path,api,transport)'
        assert s.count(needle)==1
        s=s.replace(needle,needle+'''
        # The existing startup test proves a fresh PL answer. Only after that
        # test completes may public sessions reuse the prepared model catalog.
        if answer_cache is not None:
            with coordinator.lock:
                assert coordinator.work is None
                coordinator.engine.answer_cache=answer_cache
                for conversation in coordinator.conversations.values():
                    conversation.business.answer_cache=answer_cache
            api.save(path/'ANSWER_CACHE_ENABLED.json',dict(status='VERIFIED_MODEL_CACHE_ENABLED_AFTER_REAL_PL_PROBE',
                cache=answer_cache.report(),current_model_called_for_hits=False))''')
        p.write_text(s,encoding='utf-8');changed.append(p)
        p=w/'bundle/platform/qwen35/a12/cpu01b_supervisor.py';s=p.read_text(encoding='utf-8')
        needle="self.record(event='PERMISSION', request=r,"
        assert s.count(needle)==1
        s=s.replace(needle,"self.record(event='PERMISSION', previous_durable_record_ms=getattr(self,'previous_durable_record_ms',None), request=r,")
        s=s.replace('                        record_end = time.monotonic_ns()', '                        record_end = time.monotonic_ns()\n                        self.previous_durable_record_ms=(record_end-record_start)/1000000.0')
        p.write_text(s,encoding='utf-8');changed.append(p)
        p=w/'bundle/manifest.json';m=json.loads(p.read_text())
        for row in m['files']:
            f=w/'bundle'/row['path']
            if f in changed:row.update(bytes=f.stat().st_size,sha256=sha(f))
        save(p,m);changed.append(p)
m=json.loads((NEW/'MANIFEST.json').read_text())
m['profile_id']='b601e69ca-cache-profile-v4'
for row in m['files']:
    p=NEW/row['path']
    if p in changed:row.update(bytes=p.stat().st_size,sha256=sha(p))
save(NEW/'MANIFEST.json',m);changed.append(NEW/'MANIFEST.json')
files=[dict(path=p.relative_to(NEW).as_posix(),before_sha256=sha(OLD/p.relative_to(NEW)),after_sha256=sha(p),
    gzip_base64=base64.b64encode(gzip.compress(p.read_bytes(),mtime=0)).decode()) for p in changed]
save(ROOT/'evidence/frontend_board_A/20261027-board-hotpath-opt-v1/CANDIDATE.json',dict(path=str(NEW),files=[{k:v for k,v in x.items() if k!='gzip_base64'} for x in files]))
payload='FILES='+repr(files)+'''
import base64,gzip,hashlib,json,shutil
from pathlib import Path
old=Path('/home/ubuntu/kv260-staging/a12-b601e69ca-rt-20261027-1652-v2/b601e69ca-realtime34-43-t4')
new=Path('/home/ubuntu/kv260-staging/a12-hotpath-20261027-v4/b601e69ca-cache-profile-t4')
assert not new.exists()
for f in FILES:assert hashlib.sha256((old/f['path']).read_bytes()).hexdigest()==f['before_sha256']
shutil.copytree(old,new,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for f in FILES:
    data=gzip.decompress(base64.b64decode(f['gzip_base64']));assert hashlib.sha256(data).hexdigest()==f['after_sha256']
    (new/f['path']).write_bytes(data)
result=dict(status='HOTPATH_V4_STAGED',path=str(new),changed_files=[x['path'] for x in FILES],live_window_unchanged=True)
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(result),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
'''
(EV/'stage_hotpath_v4.py').write_text(payload,encoding='utf-8')
print(json.dumps(dict(candidate=str(NEW),changed_files=len(files))))
