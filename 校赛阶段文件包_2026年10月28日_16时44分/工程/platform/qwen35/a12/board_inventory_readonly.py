"""Live inventory only: no model/device open, locks, services, or configuration writes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

def command(argv,timeout=20):
    r=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
    return dict(argv=argv,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)

def names(path):
    p=Path(path)
    return sorted(x.name for x in p.iterdir() if not x.name.startswith('.')) if p.is_dir() else None

def fileinfo(path,hash_content=False):
    p=Path(path)
    if not p.is_file():return None
    s=p.stat();row=dict(bytes=s.st_size)
    if hash_content:row['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    return row

if __name__=='__main__':
    assert os.geteuid()==0 and os.uname().machine=='aarch64'
    assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
    started=time.monotonic_ns();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    memory={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()}
    root=Path('/opt/patient-qwen')
    files={}
    for name in ('models/model.lock.json','models/sidecar_A/qwen35-v1/manifest.json','modules/linear_A/manifest.json',
        'modules/voice_A/manifest.json','config/qwen35/system.json','config/qwen35/defaults.json',
        'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'):
        p=root/name;files[name]=fileinfo(p,hash_content=p.is_file() and p.stat().st_size<1048576)
    sidecar=root/'models/sidecar_A/qwen35-v1';manifest=sidecar/'manifest.json';weights=None
    if manifest.is_file():
        m=json.loads(manifest.read_text());entries=m['entries'];weightfiles=[sidecar/r['file'] for e in entries for r in e['files'].values()]
        weights=dict(entries=len(entries),layers=sorted({e['layer'] for e in entries}),ops=sorted({e['op'] for e in entries}),
            payload_bytes=sum(p.stat().st_size for p in weightfiles),files=len(weightfiles))
    bundles={}
    for name in ('step08-diagnostic-20261024-v1','step08-generation-20261024-v1'):
        p=Path('/var/lib/kv260-a12')/name
        if p.is_dir():
            bundles[name]=dict(binary=fileinfo(p/'bin/qwen35-a12',True),xclbin=fileinfo(p/'w4a8.xclbin',True),
                hardware=names(p/'hardware'),manager_exit=json.loads((p/'manager-exit.json').read_text()) if (p/'manager-exit.json').is_file() else None)
    objects=[]
    for base in (root/'artifacts',root/'models',Path('/home/ubuntu/models')):
        if base.is_dir():
            for p in base.glob('**/*.gguf'):objects.append(dict(path=str(p),bytes=p.stat().st_size))
    usage={str(p):dict(total=shutil.disk_usage(p).total,used=shutil.disk_usage(p).used,free=shutil.disk_usage(p).free)
        for p in (Path('/'),Path('/boot/firmware')) if p.exists()}
    sizes={}
    for path in ('/opt/patient-qwen','/var/lib/kv260-a12','/var/lib/kv260-a11','/var/lib/kv260-a10','/home/ubuntu',
        '/opt/patient-qwen/artifacts','/opt/patient-qwen/models','/opt/patient-qwen/system_qwen35','/opt/patient-qwen/modules',
        '/opt/patient-qwen/runtime','/opt/patient-qwen/platform','/opt/patient-qwen/bin'):
        if Path(path).exists():sizes[path]=command(['du','-x','-B1','-s',path],60)
    firmware={p.name:names(p) for p in Path('/lib/firmware/xilinx').iterdir() if p.is_dir()}
    packages=command(['dpkg-query','-W','-f=${Package}\t${Version}\n','xrt','xmutil','dfx-mgr','python3'])
    services=command(['systemctl','list-units','--type=service','--all','--no-pager','--no-legend'])
    services['stdout']='\n'.join(l for l in services['stdout'].splitlines() if any(s in l.lower() for s in ('qwen','patient','voice','vosk','piper','whisper','dfx','gdm','ssh')))
    overlays=Path('/sys/kernel/config/device-tree/overlays')
    processes=command(['ps','-eo','pid,comm,rss,pcpu','--sort=-rss'])
    processes['stdout']='\n'.join(processes['stdout'].splitlines()[:20])
    active=Path('/var/lock/kv260-a1/active')
    old_pids={}
    for entry in bundles:
        p=Path('/var/lib/kv260-a12')/entry
        for n in ('manager-pid.json','run-v1/s1/identity.json','run-v1/s2/identity.json'):
            f=p/n
            if f.is_file():
                d=json.loads(f.read_text())
                for k in ('pid','wrapper_pid'):
                    if k in d:old_pids[str(d[k])]=not Path('/proc',str(d[k])).exists()
    row=dict(schema='BOARD_CONTENT_AND_RESOURCE_READONLY_V1',boot_id=boot,kernel=os.uname().release,
        elapsed_s=(time.monotonic_ns()-started)/1e9,memory_kib=memory,disk=usage,directory_sizes=sizes,
        top_level={str(p):names(p) for p in (root,root/'artifacts',root/'models',root/'modules',root/'bin',Path('/opt'),Path('/home/ubuntu'))},
        deployed_files=files,gguf_files=objects,sidecar=weights,bundles=bundles,firmware_packages=firmware,
        default_firmware=Path('/etc/dfx-mgrd/default_firmware').read_text().strip(),
        overlays={p.name:(p/'status').read_text().strip() for p in overlays.iterdir() if p.is_dir()},
        fpga_state=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
        zocl_present=Path('/sys/module/zocl').exists(),active_lease_exists=active.exists(),known_test_processes_absent=old_pids,
        temperatures_mC=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')],
        packages=packages,services=services,top_processes=processes,cpu_count=os.cpu_count(),loadavg=Path('/proc/loadavg').read_text().strip(),
        new_model_runs=0,PL_loads=0,service_changes=0,configuration_changes=0)
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
    print(json.dumps(row),flush=True)
