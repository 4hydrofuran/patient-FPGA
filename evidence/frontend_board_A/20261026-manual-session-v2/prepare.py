import hashlib,json,shutil,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[3];out=Path(__file__).parent
names=('interactive_case.py','interactive_entry.py','board_case.py','board_entry.py','graphical_runtime.py','verify_graphical.py','browser_bidi.py')
files={n:root/'platform/qwen35/web'/n for n in names}
files.update({'web_managed.py':root/'system_qwen35/app/web_managed.py','native_pl.py':root/'system_qwen35/app/native_pl.py'})
with zipfile.ZipFile(out/'overlay.zip','x',zipfile.ZIP_DEFLATED) as z:
    for name,path in files.items():z.write(path,name)
sha=hashlib.sha256((out/'overlay.zip').read_bytes()).hexdigest()
setup=out/'setup.py';setup.write_text(setup.read_text().replace('OVERLAY_SHA',repr(sha)))
setup_sha=hashlib.sha256(setup.read_bytes()).hexdigest()
(out/'bootstrap.py').write_text("import hashlib,urllib.request\nb=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=="+repr(setup_sha)+"\nexec(compile(b,'graphical_setup','exec'))\n")
(out/'SOURCES.json').write_text(json.dumps(dict(overlay_sha256=sha,files={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()}),indent=2))
shutil.copy2(out.parent/'20261026-manual-session-v1/serve.py',out/'serve.py')
for name in ('start','progress'):
    source=(out.parent/'20261026-manual-session-v1'/(name+'-v4.py')).read_text()
    (out/(name+'.py')).write_text(source.replace('manual-web-20261026-v4','gui-qa-20261026-v1'))
source=(out.parent/'20261026-manual-session-v1/check_local.py').read_text()
(out/'check_local.py').write_text(source)
print(json.dumps(dict(overlay_sha256=sha,bytes=(out/'overlay.zip').stat().st_size)))
