import hashlib,json
from pathlib import Path
here=Path(__file__).parent
receipt=json.loads((here/'preflight-uart.json').read_text(encoding='utf-8-sig'))
assert receipt['error'] is None
data=json.loads(receipt['output'].split('__PL_BEGIN__',1)[1].split('__PL_END__',1)[0].strip())
review=json.loads((here/'BASELINE_REVIEW.json').read_text(encoding='utf-8'))
assert review['sha256']==data['baseline_sha256'] and review['new_diagnostics_must_still_latch'] is True
(here/'preflight-local.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
source=(here/'start.py').read_text(encoding='utf-8')
assert source.count("EXPECTED_BASELINE='REVIEW_REQUIRED'")==1
source=source.replace("EXPECTED_BASELINE='REVIEW_REQUIRED'",'EXPECTED_BASELINE='+repr(data['baseline_sha256']))
(here/'start.py').write_text(source,encoding='utf-8')
for stage in ('start','collect'):
 p=here/(stage+'.py');pin=hashlib.sha256(p.read_bytes()).hexdigest()
 code=f'''import hashlib,urllib.request
from pathlib import Path
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=={data['boot_id']!r}
b=urllib.request.urlopen('http://192.168.2.1:8765/{stage}.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=={pin!r}
exec(compile(b,'reviewed_authfix_{stage}','exec'))
'''
 (here/('bootstrap-'+stage+'.py')).write_text(code,encoding='utf-8')
print(json.dumps(dict(status='REVIEWED_BINDING_PREPARED',boot_id=data['boot_id'],baseline_sha256=data['baseline_sha256'])))
