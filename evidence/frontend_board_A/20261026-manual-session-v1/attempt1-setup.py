import hashlib,json,os,shutil,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/manual-web-20261026-v1')
BASE=Path('/var/lib/kv260-a12/pl-authfix-20261026-v2/bundle')
assert os.geteuid()==0 and not Path('/var/lock/kv260-a1/active').exists()
assert not Path('/sys/module/zocl').exists()
ROOT.mkdir(mode=0o700)
raw=urllib.request.urlopen('http://192.168.2.1:8766/overlay.zip',timeout=20).read(1048576)
assert hashlib.sha256(raw).hexdigest()=='de6ae73c3037e6193a42615d2396079944a080e8a09e3d2abe81b97ff09bbbd9'
(ROOT/'overlay.zip').write_bytes(raw)
with zipfile.ZipFile(ROOT/'overlay.zip') as archive:archive.extractall(ROOT)
shutil.copytree(BASE,ROOT/'bundle',ignore=shutil.ignore_patterns('run-v1','__pycache__'))
spec=json.loads((ROOT/'bundle/control/window-spec.json').read_text())
spec.update(window_id='a12-manual-web-20261026-v1',variant='MANUAL_SINGLE_QA_PREFIX_HIT',request_limit=2,output_token_limit=24)
(ROOT/'bundle/control/window-spec.json').write_text(json.dumps(spec,indent=2))
history=ROOT/'preexisting-firmware';history.mkdir()
for name in ('a11-mlp.dtbo','a11-mlp.bit.bin'):
    p=Path('/lib/firmware')/name
    if p.exists():
        assert not p.is_symlink() and p.read_bytes()==(ROOT/'bundle/hardware'/name).read_bytes()
        p.rename(history/name)
front=Path('/home/ubuntu/patient-web-demo-20261026')
for path in (ROOT,front/'web_gateway/src',front/'.venv/lib/python3.12/site-packages'):sys.path.insert(0,str(path))
import patient_web.managed,interactive_case,interactive_entry
from board_case import load_native
load_native(ROOT,'/opt/patient-qwen')
interactive_entry.prepared_main((ROOT/'bundle/control/resource_probe_manager.py').read_text())
r=dict(status='MANUAL_WEB_INSTALLED_NOT_STARTED',root=str(ROOT),prefix_tokens=70,
       keeps_logged_in_desktop=True,automatic_question=False)
(ROOT/'installed.json').write_text(json.dumps(r))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
