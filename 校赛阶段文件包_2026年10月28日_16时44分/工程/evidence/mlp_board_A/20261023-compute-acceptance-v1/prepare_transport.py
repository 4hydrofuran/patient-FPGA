"""Prepare exact-byte staging and one detached compute launch; local only."""
import base64,gzip,hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=E.parents[2];bundle=E/'bundle-v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
old=ROOT/'platform/local/a11-mlp-20261023-v1';before=json.loads((old/'manifest.json').read_bytes())
after=json.loads((bundle/'manifest.json').read_bytes());pin=sha((bundle/'manifest.json').read_bytes())
payload={n:base64.b64encode((bundle/n).read_bytes()).decode() for n,e in after['files'].items() if before['files'].get(n)!=e}
payload['manifest.json']=base64.b64encode((bundle/'manifest.json').read_bytes()).decode()
baseline=sha((E/'preflight/kernel.raw.txt').read_bytes())
launch=(ROOT/'platform/qwen35/a11/launch_mlp_once.py').read_text().replace('a11-mlp-20261023-v1','a11-mlp-20261023-v2').replace('3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c',pin).replace('1c4e880e36fa39f3bb0c516fac2cea00ce85b03b68969500a8ef190409b78655',baseline).replace('USER_APPROVED_A11_23_SERIAL_CALLS_55C_NO_STRESS_NO_RETRY_20261023','USER_REQUESTED_A11_COMPLETE_NUMERIC_PERFORMANCE_AND_REPAIR_20261023')
# Bounded read-only resampling of transient proc races; all scans preserved.
launch=launch.replace('    scan=collect(allow_ps_display=True)','''    scans=[]
    for attempt in range(4):
        scan=collect(allow_ps_display=True);scans.append(scan)
        if scan.get('scan_complete') is True:break
        need(scan.get('boot_id')==scan.get('boot_id_after')==BOOT and
             not scan.get('device_holders') and not scan.get('device_mappings'),'unsafe preflight')
        issues=scan.get('scan_issues');need(type(issues) is list and issues,'unknown scan failure')
        for issue in issues:
            need(issue.get('reason') in ('PROCESS_SET_CHANGED','ValueError: PROCESS_OR_FD_TABLE_CHANGED'),
                 'nontransient scan failure')
        if attempt<3:time.sleep(.15)
    with (ROOT/'preflight-scans.json').open('x') as f:json.dump(scans,f)
'''.rstrip())
payload['launch_mlp_once.py']=base64.b64encode(launch.encode()).decode()
(E/'launch_mlp_v2.py').write_bytes(launch.encode())
stage='''import json,hashlib,base64,os
from pathlib import Path
old=Path('/var/lib/kv260-a11/a11-mlp-20261023-v1');new=Path('/var/lib/kv260-a11/a11-mlp-20261023-v2')
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='8422f92f-d01f-4849-ad19-6e66b640a9ad'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert not os.path.lexists('/var/lock/kv260-a1/active') and not Path('/sys/module/zocl').exists()
assert Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()=='applied'
assert hashlib.sha256((old/'manifest.json').read_bytes()).hexdigest()=='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
payload=PAYLOAD
manifest=base64.b64decode(payload['manifest.json']);assert hashlib.sha256(manifest).hexdigest()==PIN
m=json.loads(manifest);previous=json.loads((old/'manifest.json').read_bytes())
os.umask(0o077);new.mkdir(mode=0o700)
for name,e in m['files'].items():
 if name in payload:data=base64.b64decode(payload[name])
 else:
  assert previous['files'][name]==e
  data=(old/name).read_bytes()
 assert len(data)==e['bytes'] and hashlib.sha256(data).hexdigest()==e['sha256']
 target=new/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 with target.open('xb') as f:f.write(data)
for name in ('manifest.json','launch_mlp_once.py'):
 with (new/name).open('xb') as f:f.write(base64.b64decode(payload[name]))
print(json.dumps(dict(status='STAGED_NOT_EXECUTED',manifest_sha256=PIN)))
'''.replace('PAYLOAD',repr(payload)).replace('PIN',repr(pin))
(E/'stage_v2.py').write_bytes(stage.encode())
start='''import subprocess,sys,time,json
from pathlib import Path
p=Path('/var/lib/kv260-a11/a11-mlp-20261023-v2')
(p/'launch-reservation').touch(exist_ok=False)
wrapper="""import subprocess,json,os
from pathlib import Path
p=Path('/var/lib/kv260-a11/a11-mlp-20261023-v2')
out=(p/'host.stdout.jsonl').open('xb');err=(p/'host.stderr.txt').open('xb')
c=subprocess.Popen(['/usr/bin/python3','-B','-I',str(p/'launch_mlp_once.py'),'8422f92f-d01f-4849-ad19-6e66b640a9ad'],stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True)
with (p/'launcher-pid.json').open('x') as f:json.dump(dict(pid=c.pid,wrapper_pid=os.getpid()),f)
rc=c.wait();out.close();err.close()
with (p/'host-exit.json').open('x') as f:json.dump(dict(exit_code=rc,pid=c.pid),f)
"""
c=subprocess.Popen(['/usr/bin/python3','-B','-I','-c',wrapper],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
print(json.dumps(dict(wrapper_pid=c.pid,status='LAUNCHED_ONCE_NO_RETRY')),flush=True)
for i in range(90):
 if (p/'host-exit.json').exists() or (p/'STOP.json').exists():break
 time.sleep(.5)
print(json.dumps({n:(p/n).read_text() for n in ('host-exit.json','worker-result.json','STOP.json','host.stderr.txt') if (p/n).exists()}))
'''
(E/'start_v2.py').write_bytes(start.encode())
print(json.dumps(dict(manifest_sha256=pin,changed_payloads=list(payload),stage_command_encoded_bytes=len(base64.b64encode(gzip.compress(stage.encode()))))))
