"""Prepare a small, pinned pre-activation GUI compatibility delta; retain the v2 original."""
import base64,gzip,hashlib,json,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
OLD=ROOT/'release/a12_b_frontend_boardprep_20261027_v2/b601e69ca-realtime34-43-t4'
NEW=ROOT/'release/a12_b_frontend_boardrun_20261027_v3/b601e69ca-realtime34-43-t4'
EV=ROOT/'evidence/frontend_board_A/20261027-b601e69ca-board-run-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

shutil.copytree(OLD,NEW,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
names=[]
for kind in ('ordinary','continuous'):
    for name in ('interactive_case.py','verify_graphical.py'):
        relative=kind+'/'+name;shutil.copyfile(HERE/name,NEW/relative);names.append(relative)
meta=json.loads((NEW/'MANIFEST.json').read_text(encoding='utf-8'))
for row in meta['files']:
    if row['path'] in names:row.update(bytes=(NEW/row['path']).stat().st_size,sha256=sha(NEW/row['path']))
meta['profile_id']='b601e69ca-a-realtime-irq2-gui-compat-v3';save(NEW/'MANIFEST.json',meta)
names.append('MANIFEST.json')
files=[dict(path=name,before_sha256=sha(OLD/name),after_sha256=sha(NEW/name),
    gzip_base64=base64.b64encode(gzip.compress((NEW/name).read_bytes(),mtime=0)).decode()) for name in names]
save(EV/'GUI_COMPAT_PATCH.json',dict(status='PRE_ACTIVATION_DELTA_REQUIRES_APPLY_AND_TEST',files=files,
    reason='Keep model profile dict separate from Firefox profile path; verify the actually selected neutral prefix',
    native_binary_changed=False,checker_scoring_changed=False,BOARD='NOT_TESTED'))
payload='FILES='+repr(files)+r'''
import base64,gzip,hashlib,json,os
from pathlib import Path
root=Path('/home/ubuntu/kv260-staging/a12-b601e69ca-rt-20261027-1652-v2/b601e69ca-realtime34-43-t4')
result=dict(status='PENDING',machine_sha256='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec',compute_runs=0,pl_loads=0)
try:
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
    assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()==result['machine_sha256']
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='a9dd0f40-016e-4234-b73b-13546d4a62b1'
    assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
    assert not Path('/var/lib/kv260-a12/b601e69ca-realtime-20261027-v1').exists()
    backup=root.parent/'pre-gui-compat-v3';assert not backup.exists()
    for f in FILES:assert hashlib.sha256((root/f['path']).read_bytes()).hexdigest()==f['before_sha256']
    for f in FILES:
        p=backup/f['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((root/f['path']).read_bytes())
        data=gzip.decompress(base64.b64decode(f['gzip_base64']));assert hashlib.sha256(data).hexdigest()==f['after_sha256']
        (root/f['path']).write_bytes(data)
    meta=json.loads((root/'MANIFEST.json').read_text())
    for f in meta['files']:assert hashlib.sha256((root/f['path']).read_bytes()).hexdigest()==f['sha256']
    result.update(status='GUI_COMPATIBILITY_DELTA_APPLIED_MANIFEST_VERIFIED',files=[{k:v for k,v in f.items() if k!='gzip_base64'} for f in FILES],boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
except Exception as e:result.update(status='FAILED_PRESERVE_PARTIAL_STATE',error=type(e).__name__+': '+str(e))
finally:
    (root.parent/'GUI_COMPAT_V3_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(result),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
'''
(EV/'apply_gui_patch.py').write_text(payload,encoding='utf-8')
print(json.dumps(dict(candidate=str(NEW),changed_files=names,payload_sha256=sha(EV/'apply_gui_patch.py')),indent=2))
