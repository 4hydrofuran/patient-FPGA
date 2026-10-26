import hashlib,json,os,shutil,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/web-multi-20261026-v1')
BASE=Path('/var/lib/kv260-a12/pl-authfix-20261026-v2/bundle')
assert os.geteuid()==0 and not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
ROOT.mkdir(mode=0o700)
raw=urllib.request.urlopen('http://192.168.2.1:8766/overlay.zip',timeout=20).read(1048576)
assert hashlib.sha256(raw).hexdigest()=='644146ed609886fe57aff77791e037439c1d99b37f6c069237f0a1b82955d404'
(ROOT/'overlay.zip').write_bytes(raw)
with zipfile.ZipFile(ROOT/'overlay.zip') as z:z.extractall(ROOT)
shutil.copytree(BASE,ROOT/'bundle',ignore=shutil.ignore_patterns('run-v1','__pycache__'))
spec=json.loads((ROOT/'bundle/control/window-spec.json').read_text())
spec.update(window_id='a12-web-multi-20261026-v1',variant='CONTINUOUS_GUI_MULTI_SESSION',max_runs=60000,
            request_limit=2000,prompt_token_limit=1024,output_token_limit=24,max_session_seconds=14400)
(ROOT/'bundle/control/window-spec.json').write_text(json.dumps(spec,indent=2))
budget_path=ROOT/'bundle/evidence/RESOURCE_CALL_BUDGET.json';budget=json.loads(budget_path.read_text())
assert len(budget['profiles'])==1 and budget['profiles'][0]['scope']=='all'
budget['profiles'][0].update(max_successful_runs=60000,request_limit=2000,prompt_token_limit=1024,output_token_limit=24,max_session_seconds=14400)
budget['interactive_scope']='User requested continuous multiple turns and new consultations; new independent owner, not renewal of an old trial'
budget_path.write_text(json.dumps(budget,indent=2))
(ROOT/'web-config.json').write_text(json.dumps(dict(continuous=True,verify_continuous=True,
    browser_profile='/home/ubuntu/snap/firefox/common/continuous-pl-20261026-v1')))
lock=Path('/run/lock/patient-qwen-linear.lock')
if not lock.exists():fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
history=ROOT/'preexisting-firmware';history.mkdir()
for name in ('a11-mlp.dtbo','a11-mlp.bit.bin'):
    p=Path('/lib/firmware')/name
    if p.exists():
        assert not p.is_symlink() and p.read_bytes()==(ROOT/'bundle/hardware'/name).read_bytes();p.rename(history/name)
rule=Path('/run/udev/rules.d/99-patient-pl-headless.rules');rule.parent.mkdir(exist_ok=True)
text='SUBSYSTEM=="drm", KERNEL=="card[0-9]*", DRIVERS=="zocl-drm", ENV{ID_SEAT}="seat-patient-pl"\n'
if rule.exists():assert rule.read_text()==text
else:rule.write_text(text)
subprocess.run(['udevadm','control','--reload-rules'],check=True,timeout=5)
front=Path('/home/ubuntu/patient-web-demo-20261026')
for p in (ROOT,front/'web_gateway/src',front/'.venv/lib/python3.12/site-packages'):sys.path.insert(0,str(p))
import patient_web.managed,interactive_case,interactive_entry,verify_continuous
from board_case import load_native
load_native(ROOT,'/opt/patient-qwen')
interactive_entry.graphical_main((ROOT/'bundle/control/resource_probe_manager.py').read_text())
pins={name:hashlib.sha256((ROOT/'bundle'/name).read_bytes()).hexdigest() for name in ('control/resource_probe_manager.py','platform/qwen35/a12/cpu01b_window.py','platform/qwen35/a12/resource_probe_binding.py','bin/qwen35-a12')}
r=dict(status='CONTINUOUS_SERVICE_INSTALLED_NOT_STARTED',root=str(ROOT),base_pins=pins,max_runs=60000,max_seconds=14400)
(ROOT/'installed.json').write_text(json.dumps(r,indent=2))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
