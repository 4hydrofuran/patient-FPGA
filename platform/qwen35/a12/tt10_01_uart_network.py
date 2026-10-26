"""One guarded transient address restoration; preserves stale lease and boot files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
BOOT='d6d3b16f-f78c-4efa-acaa-14fc8b076fe8'
LEASE=Path('/var/lock/kv260-a1/active/lease.json')
LEASE_SHA='568d525f398a30b931f1767f4eec6ac19303814e781b1602d5756062f2a248e7'
PUB='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe'
OUT=Path('/var/lib/kv260-a12/recovery-20261025-network-v1')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def cmd(argv):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=8)
    item=dict(argv=argv,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
    r['commands'].append(item)
    return item

def ok(argv):
    item=cmd(argv)
    assert item['exit_code']==0,item
    return item['stdout']

def persist():
    # Only this fresh recovery directory is written. Never rewrite old evidence.
    with (OUT/'journal.jsonl').open('a') as f:
        f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())

r=dict(scope='TEMPORARY_ETH0_IPV4_RECOVERY_NO_COMPUTE',machine_sha256=MACHINE,
       boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
       kernel=os.uname().release,commands=[],actions=[],boot_hashes={},
       compute_runs=0,pl_loads=0,reboots=0,lease_modified=False,
       persistent_network_configuration_written=False,status='GUARDS_PENDING')
created=False
try:
    assert os.geteuid()==0 and sha('/etc/machine-id')==MACHINE
    assert r['boot_id']==BOOT and r['kernel']=='6.8.0-1036-xilinx'
    assert Path('/sys/class/net/eth0/address').read_text().strip()=='00:0a:35:0f:2d:70'
    assert Path('/sys/class/net/eth0/carrier').read_text().strip()=='1'
    assert sha(LEASE)==LEASE_SHA and not Path('/sys/module/zocl').exists()
    assert Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()=='applied'
    assert not any(Path('/proc',str(pid)).exists() for pid in (167484,167575))
    assert ' '.join(Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()[:2])==PUB
    addresses=json.loads(ok(['ip','-j','-4','addr','show','dev','eth0']))
    # iproute2 omits an interface entirely from `-4 addr` when it has no IPv4.
    assert addresses==[] or (len(addresses)==1 and addresses[0]['ifname']=='eth0' and not addresses[0]['addr_info']),'Unexpected IPv4; no takeover'
    assert json.loads(ok(['ip','-j','-4','route','show']))==[],'Unexpected routes'
    r['before_ssh_listeners']=ok(['ss','-H','-ltnp','sport = :22'])
    r['before_ssh_service']=cmd(['systemctl','is-active','ssh.service'])
    r['before_ssh_socket']=cmd(['systemctl','is-active','ssh.socket'])
    for name in ('image.fit','boot.scr.uimg','a10-candidate-irq2-20261021.fit'):
        p=Path('/boot/firmware')/name
        r['boot_hashes'][name]=dict(bytes=p.stat().st_size,sha256=sha(p))
    assert r['boot_hashes']['a10-candidate-irq2-20261021.fit']['sha256']=='e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'
    OUT.mkdir(mode=0o700,exist_ok=False);created=True
    r['status']='GUARDS_PASSED_BEFORE_ADDRESS_ADD';persist()
    r['actions'].append('ip addr add 192.168.2.2/24 dev eth0');persist()
    ok(['ip','addr','add','192.168.2.2/24','dev','eth0']);persist()
    if not r['before_ssh_listeners'].strip():
        r['actions'].append('systemctl start ssh.service');persist()
        ok(['systemctl','start','ssh.service']);persist()
    r['after_ip']=json.loads(ok(['ip','-j','-4','addr','show','dev','eth0']))
    assert [(a['local'],a['prefixlen']) for a in r['after_ip'][0]['addr_info']]==[('192.168.2.2',24)]
    r['after_routes']=json.loads(ok(['ip','-j','-4','route','show']))
    r['after_ssh_listeners']=ok(['ss','-H','-ltnp','sport = :22'])
    assert r['after_ssh_listeners'].strip(),'SSH not listening'
    assert sha(LEASE)==LEASE_SHA
    assert all(sha(Path('/boot/firmware')/n)==v['sha256'] for n,v in r['boot_hashes'].items())
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
    r['status']='TEMPORARY_NETWORK_RESTORED_SSH_HOST_PIN_MATCHED'
except Exception as exc:
    r['status']='FAILED_PRESERVE_PARTIAL_STATE';r['error']=type(exc).__name__+': '+str(exc)
finally:
    r['observed_monotonic_ns']=time.monotonic_ns()
    if created:persist()
    print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True)
    print(json.dumps(r),flush=True)
    print('__TT10_UART_ROOT_SCENE_END__',flush=True)
