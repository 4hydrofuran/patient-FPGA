import hashlib,json,os,subprocess,urllib.request,zipfile
from pathlib import Path
root=Path('/var/lib/kv260-a12/web-20261026-v1')
assert (root/'bundle/run-v1/result.json').is_file()
assert not Path('/var/lock/kv260-a1/active').exists()
files=[root/n for n in ('installed.json','started.json','manager.stdout','manager.stderr',
       'board_entry.py','board_case.py','web_managed.py','native_pl.py','browser_bidi.py')]
files += [p for p in (root/'bundle/run-v1').rglob('*') if p.is_file()]
archive=root/'receipt.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(root).as_posix())
size=archive.stat().st_size
with archive.open('rb') as f:
    result=urllib.request.urlopen(urllib.request.Request('http://192.168.2.1:8766/receipt.zip',
        data=f,headers={'Content-Length':str(size)},method='POST'),timeout=30).read(100)
assert result==b'RECEIVED'
report=dict(status='WEB_RECEIPTS_EXPORTED',bytes=size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,
    active=Path('/var/lock/kv260-a1/active').exists(),zocl=Path('/sys/module/zocl').exists(),
    overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()},
    gdm=subprocess.run(['systemctl','is-active','gdm'],capture_output=True,text=True).stdout.strip())
print('__PL_BEGIN__');print(json.dumps(report));print('__PL_END__')
