import hashlib,urllib.request
from pathlib import Path
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='0978088a-8d10-45b2-8f43-726d00209313'
b=urllib.request.urlopen('http://192.168.2.1:8765/start.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='4160504db452624ed009e18db8d6b97abc28d317eb43d92a4edc891ff20a10cc'
exec(compile(b,'reviewed_authfix_start','exec'))
