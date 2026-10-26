import hashlib,json,shutil,zipfile
from pathlib import Path
out=Path(__file__).parent;root=out.parents[2]
shutil.copy2(out/'setup.py',out/'setup-v3.py');shutil.copy2(out/'overlay.zip',out/'overlay-v3.zip')
files={n:root/'platform/qwen35/web'/n for n in ('interactive_case.py','interactive_entry.py','board_case.py','board_entry.py')}
files.update({'web_managed.py':root/'system_qwen35/app/web_managed.py','native_pl.py':root/'system_qwen35/app/native_pl.py'})
with zipfile.ZipFile(out/'overlay.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name,path in files.items():z.write(path,name)
sha=hashlib.sha256((out/'overlay.zip').read_bytes()).hexdigest()
old=json.loads((out/'SOURCES-v2.json').read_text())['overlay_sha256']
source=(out/'setup.py').read_text().replace('manual-web-20261026-v3','manual-web-20261026-v4').replace(old,sha)
(out/'setup.py').write_text(source)
setup_sha=hashlib.sha256((out/'setup.py').read_bytes()).hexdigest()
(out/'bootstrap-v4.py').write_text("import hashlib,urllib.request\nb=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=="+repr(setup_sha)+"\nexec(compile(b,'manual_setup_v4','exec'))\n")
for name in ('start','progress'):
    (out/(name+'-v4.py')).write_text((out/(name+'-v3.py')).read_text().replace('manual-web-20261026-v3','manual-web-20261026-v4'))
(out/'SOURCES-v4.json').write_text(json.dumps(dict(overlay_sha256=sha,files={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()}),indent=2))
source=(out/'close_warmed_v3.py').read_bytes();(out/'collect.py').write_bytes(source)
source_sha=hashlib.sha256(source).hexdigest()
(out/'close-warmed-bootstrap.py').write_text("import hashlib,urllib.request\nb=urllib.request.urlopen('http://192.168.2.1:8766/collect.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=="+repr(source_sha)+"\nexec(compile(b,'close_warmed_v3','exec'))\n")
