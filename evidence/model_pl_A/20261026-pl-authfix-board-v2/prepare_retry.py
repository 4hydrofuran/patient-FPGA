import hashlib,json
from pathlib import Path
here=Path(__file__).parent
source=(here/'start.py').read_text(encoding='utf-8')
anchor="entry=ROOT/'run_bound_original.py'"
assert source.count(anchor)==1
replacement="""assert not Path('/var/lock/kv260-a1/active').exists()
assert not Path('/sys/module/zocl').exists()
assert not Path('/lib/firmware/xilinx/a12-pl-authfix-20261026-v2').exists()
assert not (BUNDLE/'run-v1/s2/ready.json').exists()
archive=ROOT/'setup-attempt-01';archive.mkdir(mode=0o700)
(BUNDLE/'run-v1').rename(archive/'run-v1')
for name in ('manager.stdout','manager.stderr','ATTEMPT_RESULT.json','run_bound_original.py'):
 (ROOT/name).rename(archive/name)
entry=ROOT/'run_bound_original2.py'"""
source=source.replace(anchor,replacement)
(here/'start2.py').write_text(source,encoding='utf-8')
boot=json.loads((here/'preflight-local.json').read_text(encoding='utf-8'))['boot_id']
for stage in ('start2','collect'):
 pin=hashlib.sha256((here/(stage+'.py')).read_bytes()).hexdigest()
 (here/('bootstrap-'+stage+'.py')).write_text(f"import hashlib,urllib.request\nfrom pathlib import Path\nassert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=={boot!r}\nb=urllib.request.urlopen('http://192.168.2.1:8765/{stage}.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=={pin!r}\nexec(compile(b,'reviewed_authfix_{stage}','exec'))\n",encoding='utf-8')

