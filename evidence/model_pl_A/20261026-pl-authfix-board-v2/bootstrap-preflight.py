import hashlib,os,subprocess,urllib.request
from pathlib import Path
assert os.uname().release=='6.8.12-a10irq2'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='b0718166-5c3b-4c4f-b669-4f83d3340d00'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
addresses=subprocess.check_output(['ip','-j','-4','addr','show','dev','eth0'],text=True)
if '192.168.2.2' not in addresses:subprocess.run(['nmcli','--wait','8','device','modify','eth0','+ipv4.addresses','192.168.2.2/24'],check=True,capture_output=True)
b=urllib.request.urlopen('http://192.168.2.1:8765/preflight.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='1c63877941ec3abcf176c319aef85b2eb34f9b3cbcfba9f5c276fbeafb29549d'
exec(compile(b,'reviewed_authfix_preflight','exec'))
