"""Restore only the authorized volatile direct address after exact boot identity."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

def main(boot):
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
    assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
    assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
    assert Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()=='applied'
    assert Path('/sys/class/net/eth0/carrier').read_text().strip()=='1'
    descriptors=[]
    for name in ('/var/lock/kv260-a1/deployment.lock','/run/lock/patient-qwen-linear.lock'):
        fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        s=os.fstat(fd);assert s.st_uid==0 and stat.S_ISREG(s.st_mode)
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);descriptors.append(fd)
    def addresses():
        links=json.loads(subprocess.check_output(['ip','-j','addr','show','dev','eth0']))
        assert len(links)==1 and links[0]['ifname']=='eth0'
        return [x for x in links[0]['addr_info'] if x['family']=='inet']
    before=addresses();wanted=[x for x in before if x['local']=='192.168.2.2' and x['prefixlen']==24]
    assert not before or len(before)==len(wanted)==1,'Unexpected IPv4: no deletion or replacement'
    if not before:subprocess.run(['ip','addr','add','192.168.2.2/24','dev','eth0'],check=True,timeout=5)
    after=addresses();assert len(after)==1 and after[0]['local']=='192.168.2.2' and after[0]['prefixlen']==24
    print(json.dumps(dict(status='VOLATILE_DIRECT_ADDRESS_VERIFIED',boot_id=boot,before=before,after=after,
        persistent_network_changed=False,reboot_commands=0,PL_changes=0,model_submissions=0)),flush=True)
    for fd in descriptors:os.close(fd)

if __name__=='__main__':main(sys.argv[1])
