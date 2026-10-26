import hashlib,json,os,shutil,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/web-20261026-v1')
BASE=Path('/var/lib/kv260-a12/pl-authfix-20261026-v2/bundle')
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
ROOT.mkdir(mode=0o700)
raw=urllib.request.urlopen('http://192.168.2.1:8766/overlay.zip',timeout=20).read(1048576)
assert hashlib.sha256(raw).hexdigest()=='042e0d91af93c8771796c5334826b91766d8044dfa5f835c3a73dcec3db6e203'
(ROOT/'overlay.zip').write_bytes(raw)
with zipfile.ZipFile(ROOT/'overlay.zip') as archive:archive.extractall(ROOT)
shutil.copytree(BASE,ROOT/'bundle',ignore=shutil.ignore_patterns('run-v1','__pycache__'))
spec=json.loads((ROOT/'bundle/control/window-spec.json').read_text())
spec.update(window_id='a12-web-20261026-v1',variant='WEB_SINGLE_QA',request_limit=1,output_token_limit=24)
(ROOT/'bundle/control/window-spec.json').write_text(json.dumps(spec,indent=2))
history=ROOT/'preexisting-firmware';history.mkdir()
for name in ('a11-mlp.dtbo','a11-mlp.bit.bin'):
    p=Path('/lib/firmware')/name
    if p.exists():
        assert not p.is_symlink() and p.read_bytes()==(ROOT/'bundle/hardware'/name).read_bytes()
        p.rename(history/name)
front=Path('/home/ubuntu/patient-web-demo-20261026')
for path in (ROOT,front/'web_gateway/src',front/'.venv/lib/python3.12/site-packages'):
    sys.path.insert(0,str(path))
import patient_web.managed,uvicorn,board_case,board_entry
native_class=board_case.load_native(ROOT,'/opt/patient-qwen')
board_entry.prepared_main((ROOT/'bundle/control/resource_probe_manager.py').read_text())
report=dict(status='WEB_OVERLAY_INSTALLED_IMPORTS_VERIFIED_NOT_STARTED',root=str(ROOT),
    native_class=native_class.__name__,frontend=patient_web.managed.__file__,
    uvicorn=uvicorn.__version__,source_manager_sha256=hashlib.sha256((ROOT/'bundle/control/resource_probe_manager.py').read_bytes()).hexdigest(),
    source_native_sha256=hashlib.sha256((ROOT/'native_pl.py').read_bytes()).hexdigest(),PL_actions=0)
(ROOT/'installed.json').write_text(json.dumps(report,indent=2))
print('__PL_BEGIN__');print(json.dumps(report));print('__PL_END__')
