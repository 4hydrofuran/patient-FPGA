import ast,hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[3]
out=Path(__file__).parent
source=(root/'evidence/frontend_board_A/20261026-inspect-v1/interactive_check.py').read_text()
node=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='Bidi')
bidi='import os,json,socket,struct,base64\n'+''.join(source.splitlines(True)[node.lineno-1:node.end_lineno])
(out/'browser_bidi.py').write_text(bidi,encoding='utf-8')
files={'board_case.py':root/'platform/qwen35/web/board_case.py',
       'board_entry.py':root/'platform/qwen35/web/board_entry.py',
       'web_managed.py':root/'system_qwen35/app/web_managed.py',
       'native_pl.py':root/'system_qwen35/app/native_pl.py',
       'browser_bidi.py':out/'browser_bidi.py'}
with zipfile.ZipFile(out/'overlay.zip','x',zipfile.ZIP_DEFLATED) as z:
    for name,path in files.items():z.write(path,name)
sha=hashlib.sha256((out/'overlay.zip').read_bytes()).hexdigest()
path=out/'setup.py'
path.write_text(path.read_text(encoding='utf-8').replace('OVERLAY_SHA',repr(sha)),encoding='utf-8')
setup_sha=hashlib.sha256(path.read_bytes()).hexdigest()
bootstrap="import hashlib,urllib.request\nb=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)\nassert hashlib.sha256(b).hexdigest()=="+repr(setup_sha)+"\nexec(compile(b,'web_setup','exec'))\n"
(out/'bootstrap.py').write_text(bootstrap,encoding='utf-8')
(out/'SOURCES.json').write_text(json.dumps(dict(overlay_sha256=sha,
    files={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()}),indent=2))
print(json.dumps(dict(overlay_sha256=sha,bytes=(out/'overlay.zip').stat().st_size)))
