"""Prepare fixed-source UART downloads from reviewed local source files."""
import hashlib,json,re
from pathlib import Path
here=Path(__file__).parent
identity=json.loads((here/'identity-irq2-v3.json').read_text(encoding='utf-8-sig'))
raw=identity['raw']
assert '6.8.12-a10irq2' in raw
boot=re.findall(r'(?m)^([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\r?$',raw)[-1]
preflight=here/'preflight.py'
pin=hashlib.sha256(preflight.read_bytes()).hexdigest()
code=f'''import hashlib,os,subprocess,urllib.request
from pathlib import Path
assert os.uname().release=='6.8.12-a10irq2'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=={boot!r}
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
addresses=subprocess.check_output(['ip','-j','-4','addr','show','dev','eth0'],text=True)
if '192.168.2.2' not in addresses:subprocess.run(['nmcli','--wait','8','device','modify','eth0','+ipv4.addresses','192.168.2.2/24'],check=True,capture_output=True)
b=urllib.request.urlopen('http://192.168.2.1:8765/preflight.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=={pin!r}
exec(compile(b,'reviewed_authfix_preflight','exec'))
'''
(here/'bootstrap-preflight.py').write_text(code)
print(json.dumps(dict(boot_id=boot,preflight_sha256=pin)))
