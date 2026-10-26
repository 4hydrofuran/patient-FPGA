import hashlib,json,shutil,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[3];out=Path(__file__).parent
for name in ('overlay.zip','setup.py','SOURCES.json'):
    p=out/name
    shutil.copy2(p,out/('attempt1-'+name))
files={n:root/'platform/qwen35/web'/n for n in ('interactive_case.py','interactive_entry.py','board_case.py','board_entry.py')}
files.update({'web_managed.py':root/'system_qwen35/app/web_managed.py','native_pl.py':root/'system_qwen35/app/native_pl.py'})
with zipfile.ZipFile(out/'overlay.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name,path in files.items():z.write(path,name)
sha=hashlib.sha256((out/'overlay.zip').read_bytes()).hexdigest()
source=(out/'attempt1-setup.py').read_text().replace('manual-web-20261026-v1','manual-web-20261026-v2').replace('MANUAL_SINGLE_QA_PREFIX_HIT','MANUAL_GRAPHICAL_ACTUAL_BO_PREFIX_HIT')
source=source.replace('de6ae73c3037e6193a42615d2396079944a080e8a09e3d2abe81b97ff09bbbd9',sha)
(out/'setup.py').write_text(source)
setup_sha=hashlib.sha256((out/'setup.py').read_bytes()).hexdigest()
(out/'bootstrap-v2.py').write_text("import hashlib,urllib.request\nb=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=="+repr(setup_sha)+"\nexec(compile(b,'manual_setup_v2','exec'))\n")
(out/'start-v2.py').write_text((out/'start.py').read_text().replace('manual-web-20261026-v1','manual-web-20261026-v2'))
(out/'progress-v2.py').write_text((out/'progress.py').read_text().replace('manual-web-20261026-v1','manual-web-20261026-v2'))
(out/'SOURCES-v2.json').write_text(json.dumps(dict(overlay_sha256=sha,files={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()}),indent=2))
print(json.dumps(dict(overlay_sha256=sha,bytes=(out/'overlay.zip').stat().st_size)))
