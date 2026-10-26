import io,json,os,subprocess,time,urllib.request,zipfile
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v4');run=root/'bundle/run-v1'
status=json.load(urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=3))
with urllib.request.urlopen('http://127.0.0.1:8000/',timeout=3) as f:page=dict(status=f.status,bytes=len(f.read()))
started=json.loads((root/'started.json').read_text());ready=json.loads((run/'s2/INTERACTIVE_READY.json').read_text())
rule=Path('/run/udev/rules.d/99-patient-pl-headless.rules')
browsers=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        args=(p/'cmdline').read_bytes().split(b'\0')
        if b'--kiosk' in args and b'http://127.0.0.1:8000/' in args:browsers.append(int(p.name))
    except (FileNotFoundError,PermissionError):pass
result=dict(status='LIVE_WEB_READY_FOR_MANUAL_ONE_QUESTION',physical_domain='BOARD',http_page=page,
 web_status=status,window=ready,manager_pid=started['pid'],browser_pids=browsers,
 remaining_seconds=(ready['expires_monotonic_ns']-time.monotonic_ns())/1e9,
 desktop_separation_rule=rule.read_text(),manual_question_verification='NOT_TESTED',medical_review='PENDING_TEACHER_REVIEW')
(root/'BASIC_READY.json').write_text(json.dumps(result,indent=2))
files=[root/n for n in ('BASIC_READY.json','started.json','ime-install-result.json','ime-configured.json','ime-install.log','manager.stderr')]
files+=list(run.glob('pre-allocation-admission.json'))
files+=[run/'s2'/n for n in ('ready.json','warm-result.json','graphical-allocation.json','INTERACTIVE_READY.json','browser.log')]
for version,filename in (('v1','prepl-abort.json'),('v2','idle-close.json'),('v3','warmed-close.json')):
    p=Path('/var/lib/kv260-a12/manual-web-20261026-'+version)/filename
    files.append(p)
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files:
        if p.is_file():z.write(p,p.relative_to(root.parent))
request=urllib.request.Request('http://192.168.2.1:8766/receipt.zip',data=b.getvalue(),method='POST')
with urllib.request.urlopen(request,timeout=10) as f:assert f.read()==b'RECEIVED'
print('__PL_BEGIN__');print(json.dumps(result));print('__PL_END__')
