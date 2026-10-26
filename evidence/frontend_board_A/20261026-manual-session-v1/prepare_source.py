import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
out=Path(__file__).parent
files={n:ROOT/'platform/qwen35/web'/n for n in ('interactive_case.py','interactive_entry.py','board_case.py','board_entry.py')}
files.update({'web_managed.py':ROOT/'system_qwen35/app/web_managed.py','native_pl.py':ROOT/'system_qwen35/app/native_pl.py'})
with zipfile.ZipFile(out/'overlay.zip','x',zipfile.ZIP_DEFLATED) as z:
    for name,path in files.items():z.write(path,name)
sha=hashlib.sha256((out/'overlay.zip').read_bytes()).hexdigest()
setup=out/'setup.py';setup.write_text(setup.read_text().replace('OVERLAY_SHA',repr(sha)))
setup_sha=hashlib.sha256(setup.read_bytes()).hexdigest()
(out/'bootstrap.py').write_text("import hashlib,urllib.request\nb=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=="+repr(setup_sha)+"\nexec(compile(b,'manual_setup','exec'))\n")
(out/'SOURCES.json').write_text(json.dumps(dict(overlay_sha256=sha,files={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()}),indent=2))
print(json.dumps(dict(overlay_sha256=sha,bytes=(out/'overlay.zip').stat().st_size)))
