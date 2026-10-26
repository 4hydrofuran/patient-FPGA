import hashlib,shutil
from pathlib import Path
out=Path(__file__).parent
shutil.copy2(out/'setup.py',out/'setup-attempt1.py')
source=(out/'setup.py').read_text().replace('gui-qa-20261026-v1','gui-qa-20261026-v2')
insert="lock=Path('/run/lock/patient-qwen-linear.lock')\nif not lock.exists():\n    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)\n"
source=source.replace('ROOT.mkdir(mode=0o700)',insert+'ROOT.mkdir(mode=0o700)')
(out/'setup.py').write_text(source)
sha=hashlib.sha256((out/'setup.py').read_bytes()).hexdigest()
(out/'bootstrap-retry.py').write_text("import hashlib,urllib.request\nb=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=="+repr(sha)+"\nexec(compile(b,'graphical_setup_retry','exec'))\n")
for name in ('start','progress','verification_status'):
    (out/(name+'-retry.py')).write_text((out/(name+'.py')).read_text().replace('gui-qa-20261026-v1','gui-qa-20261026-v2'))
