import hashlib,shutil
from pathlib import Path
out=Path(__file__).parent
shutil.copy2(out/'setup.py',out/'setup-v2.py')
(out/'setup.py').write_text((out/'setup.py').read_text().replace('manual-web-20261026-v2','manual-web-20261026-v3'))
sha=hashlib.sha256((out/'setup.py').read_bytes()).hexdigest()
(out/'bootstrap-v3.py').write_text("import hashlib,urllib.request\nb=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=="+repr(sha)+"\nexec(compile(b,'manual_setup_v3','exec'))\n")
for name in ('start','progress'):
    (out/(name+'-v3.py')).write_text((out/(name+'-v2.py')).read_text().replace('manual-web-20261026-v2','manual-web-20261026-v3'))
