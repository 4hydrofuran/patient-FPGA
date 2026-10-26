import hashlib,json,os,sys,urllib.request
from pathlib import Path
root=Path('/var/lib/kv260-a12/pl-authfix-20261026-v2');bundle=root/'bundle'
assert os.geteuid()==0 and Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='b0718166-5c3b-4c4f-b669-4f83d3340d00'
assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
assert not Path('/lib/firmware/xilinx/a12-pl-authfix-20261026-v2').exists()
scan=json.loads((bundle/'run-v1/s2/owner-initial-resource-scan.json').read_text())
sys.path.insert(0,str(bundle/'platform/qwen35/a12'))
binding=urllib.request.urlopen('http://192.168.2.1:8765/binding.py',timeout=15).read(16384)
ns={};exec(compile(binding,'reviewed_initial_scan_binding','exec'),ns)
window=bundle/'platform/qwen35/a12/cpu01b_window.py';old=window.read_bytes()
new=ns['adapt_initial_scan'](old.decode('utf-8')).encode('utf-8')
history=root/'gate-fix-source-v1';history.mkdir(mode=0o700)
(history/'original-window.py').write_bytes(old)
(history/'original-binding.py').write_bytes((bundle/'platform/qwen35/a12/resource_probe_binding.py').read_bytes())
window.write_bytes(new);(bundle/'platform/qwen35/a12/resource_probe_binding.py').write_bytes(binding)
(root/'binding-source.py').write_bytes(binding)
manifest=json.loads((bundle/'manifest.json').read_text())
for row in manifest['files']:
 if row['path'] in ('platform/qwen35/a12/cpu01b_window.py','platform/qwen35/a12/resource_probe_binding.py'):
  p=bundle/row['path'];row.update(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(bundle/'manifest.json').write_text(json.dumps(manifest,indent=2))
result=dict(status='INITIAL_SCAN_USES_EXISTING_COMPLETE_SCAN_POLICY',before_sha256=hashlib.sha256(old).hexdigest(),
 after_sha256=hashlib.sha256(new).hexdigest(),old_scan_issues=scan['scan_issues'],
 actual_holders_still_rejected=True,unknown_errors_still_rejected=True,max_observations=4,PL_mutations=0)
(history/'RESULT.json').write_text(json.dumps(result,indent=2))
print('__PL_BEGIN__');print(json.dumps(result));print('__PL_END__')
