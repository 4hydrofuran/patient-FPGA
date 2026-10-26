import json,os,subprocess
from pathlib import Path
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='8a0276fb-86d1-4ef8-b067-adcc903a999a'
before=subprocess.check_output(['ip','-j','-4','addr','show','dev','eth0'],text=True)
if '192.168.2.2' not in before:
    subprocess.run(['nmcli','--wait','8','device','modify','eth0','+ipv4.addresses','192.168.2.2/24'],check=True,capture_output=True)
after=subprocess.check_output(['ip','-j','-4','addr','show','dev','eth0'],text=True)
assert '192.168.2.2' in after
print(json.dumps(dict(status='TEMPORARY_DEVICE_ADDRESS_READY',addresses=json.loads(after),persistent_connection_files_modified=False)))
