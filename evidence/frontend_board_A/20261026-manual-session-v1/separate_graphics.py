import json,subprocess,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v2')
assert json.loads((Path('/var/lock/kv260-a1/active/lease.json')).read_text())['window']=='a12-manual-web-20261026-v2'
assert not (root/'bundle/run-v1/s2/worker').exists()
card=Path('/sys/class/drm/card1')
assert (card/'device/driver').resolve().name=='zocl-drm'
rule=Path('/run/udev/rules.d/99-patient-pl-headless.rules');rule.parent.mkdir(exist_ok=True)
text='SUBSYSTEM=="drm", KERNEL=="card[0-9]*", DRIVERS=="zocl-drm", ENV{ID_SEAT}="seat-patient-pl"\n'
if rule.exists():assert rule.read_text()==text
else:rule.write_text(text)
results=[]
for argv in (['udevadm','control','--reload-rules'],['udevadm','trigger','--action=change',str(card)],['udevadm','settle','--timeout=5']):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=8);results.append(dict(argv=argv,exit=p.returncode,stdout=p.stdout,stderr=p.stderr));assert p.returncode==0
time.sleep(1)
p=subprocess.run(['udevadm','info','--query=property','--path='+str(card)],capture_output=True,text=True)
results.append(dict(properties=p.stdout))
print('__PL_BEGIN__');print(json.dumps(results));print('__PL_END__')
