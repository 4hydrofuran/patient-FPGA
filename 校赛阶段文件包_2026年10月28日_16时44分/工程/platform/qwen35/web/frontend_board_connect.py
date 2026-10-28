"""Current-boot additive connection prep and preservation of a proven previous-boot lease."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
BOOT='624d896f-3a30-4c85-990c-1970373d2d28'
OLD='3dbdcb94-703e-4515-a6ff-fc2bc5923399'
LEASE_SHA='926c1d865d6a6722d1adabbcb46a81b9f26bd025e6e77a3d2182329b67973075'
CENTRAL=Path('/var/lock/kv260-a1');ACTIVE=CENTRAL/'active';OUT=Path('/var/lib/kv260-a12/preboard-b601e69ca-20261027-v1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(argv):
    r=subprocess.run(argv,capture_output=True,text=True,timeout=8)
    record=dict(argv=argv,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
    result['commands'].append(record)
    assert r.returncode==0,record
    return r.stdout
result=dict(scope='PREBOARD_CONNECTION_AND_OLD_BOOT_RECORD_PRESERVATION',machine_sha256=MACHINE,boot_id=BOOT,
    commands=[],actions=[],compute_runs=0,pl_loads=0,reboots=0,persistent_network_changes=False,old_worker_close_proven=False,status='PENDING')
fds=[]
try:
    assert os.geteuid()==0 and sha(Path('/etc/machine-id'))==MACHINE
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT and os.uname().release=='6.8.0-1036-xilinx'
    assert Path('/sys/class/net/eth0/address').read_text().strip()=='00:0a:35:0f:2d:70'
    assert Path('/sys/class/net/eth0/carrier').read_text().strip()=='1'
    assert not Path('/sys/module/zocl').exists()
    assert Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()=='applied'
    assert not ACTIVE.is_symlink() and sha(ACTIVE/'lease.json')==LEASE_SHA
    lease=json.loads((ACTIVE/'lease.json').read_text())
    assert lease['identity']==MACHINE+':'+OLD and lease['pid']==2682 and not Path('/proc/2682').exists()
    assert sha(Path('/boot/firmware/a10-candidate-irq2-20261021.fit'))=='e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'
    result['irq2_fit_sha256']='e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'
    for p in (CENTRAL/'deployment.lock',Path('/run/lock/patient-qwen-linear.lock')):
        assert not p.is_symlink()
        fd=os.open(p,os.O_RDWR|os.O_CREAT|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fds.append(fd)
    before=json.loads(command(['ip','-j','-4','addr','show','dev','eth0']))
    result['before_addresses']=before;route=command(['ip','-4','route','show','default'])
    history=CENTRAL/'history';history.mkdir(exist_ok=True)
    target=history/('previous-boot-web-modes-20261027-012930-'+BOOT[:8])
    assert not target.exists() and not OUT.exists()
    OUT.mkdir(mode=0o700)
    assert sha(ACTIVE/'lease.json')==LEASE_SHA
    ACTIVE.rename(target)
    assert sha(target/'lease.json')==LEASE_SHA
    result['actions'].append(dict(action='ARCHIVE_PREVIOUS_BOOT_LEASE',source=str(ACTIVE),target=str(target),sha256=LEASE_SHA,
        classification='PREVIOUS_BOOT_RECORD_PRESERVED_NOT_NORMAL_WORKER_RELEASE'))
    info=before[0]['addr_info'];addresses={(x['local'],x['prefixlen']) for x in info}
    if ('192.168.2.2',24) not in addresses:
        command(['ip','addr','add','192.168.2.2/24','dev','eth0']);result['actions'].append(dict(action='ADD_TEMPORARY_IPV4',address='192.168.2.2/24'))
    after=json.loads(command(['ip','-j','-4','addr','show','dev','eth0']))
    assert {(x['local'],x['prefixlen']) for x in after[0]['addr_info']}==addresses|{('192.168.2.2',24)}
    assert command(['ip','-4','route','show','default'])==route
    result['after_addresses']=after;result['active_lease_after']=ACTIVE.exists()
    result['status']='PREPARED_TEMP_NETWORK_PREVIOUS_BOOT_LEASE_ARCHIVED_NO_COMPUTE'
except Exception as e:
    result['status']='FAILED_PRESERVE_PARTIAL_STATE';result['error']=type(e).__name__+': '+str(e)
finally:
    result['observed_monotonic_ns']=time.monotonic_ns()
    if OUT.exists():(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    for fd in reversed(fds):os.close(fd)
    print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(result),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
