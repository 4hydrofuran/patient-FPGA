import hashlib,json
from pathlib import Path
here=Path(__file__).parent
boot=json.loads((here/'preflight-local.json').read_text(encoding='utf-8'))['boot_id']
pin=hashlib.sha256((here/'collect.py').read_bytes()).hexdigest()
code=f"import hashlib,urllib.request\nfrom pathlib import Path\nassert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=={boot!r}\nb=urllib.request.urlopen('http://192.168.2.1:8765/collect.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=={pin!r}\nexec(compile(b,'reviewed_authfix_collection','exec'))\n"
(here/'bootstrap-collect.py').write_text(code,encoding='utf-8')
