import os,json,subprocess,time,socket,urllib.request,hashlib
from pathlib import Path
base=Path('/home/ubuntu/patient-web-demo-20261026')
out=base/'inspection-20261026-v1'
out.mkdir(exist_ok=False)
shot=Path.home()/'snap/firefox/common/frontend-check-20261026-v1'
shot.mkdir(exist_ok=False)
r={'scope':'BOARD_FIREFOX_AND_RULE_DEMO_ONLY_NO_REAL_MODEL_OR_PL','output':str(out),'browser_screenshot':str(shot/'home.png')}
up=json.loads((base/'web_gateway/UPSTREAM.json').read_text())
r['reference_files']=[dict(source=x['source'],expected=x['sha256'],actual=hashlib.sha256((base/'web_gateway'/x['local']).read_bytes()).hexdigest()) for x in up['files']]
s=socket.socket();s.bind(('127.0.0.1',8000));s.close()
log=(out/'server.log').open('xb')
server=subprocess.Popen([str(base/'start-demo.sh')],stdout=log,stderr=subprocess.STDOUT)
r['owned_server_pid']=server.pid
try:
    for i in range(80):
        if server.poll() is not None:raise RuntimeError('Demo server exited before readiness')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=1) as f:r['status']=json.load(f)
            break
        except OSError:time.sleep(.25)
    else:raise RuntimeError('No demo readiness')
    with urllib.request.urlopen('http://127.0.0.1:8000/openapi.json',timeout=3) as f:
        schema=json.load(f);r['api_paths']=list(schema.get('paths',{}))
    browser=subprocess.Popen(['/snap/bin/firefox','--headless','--no-remote','--profile',str(shot/'profile'),'--window-size','1024,600','--screenshot',str(shot/'home.png'),'http://127.0.0.1:8000/'],stdout=(out/'firefox.out').open('wb'),stderr=(out/'firefox.err').open('wb'))
    r['owned_browser_pid']=browser.pid
    try:r['firefox_rc']=browser.wait(timeout=55)
    except subprocess.TimeoutExpired:
        r['firefox_rc']=None;r['firefox_timeout']=True
        browser.terminate()
        try:browser.wait(timeout=8)
        except subprocess.TimeoutExpired:r['browser_still_running']=True
    if (shot/'home.png').exists():
        raw=(shot/'home.png').read_bytes();r['screenshot_bytes']=len(raw);r['screenshot_sha256']=hashlib.sha256(raw).hexdigest()
    r['firefox_stdout']=(out/'firefox.out').read_text(errors='replace')[-2500:]
    r['firefox_stderr']=(out/'firefox.err').read_text(errors='replace')[-4000:]
    a=subprocess.run([str(base/'.venv/bin/python'),'-m','patient_web.acceptance','--base-url','http://127.0.0.1:8000','--expected-backend','demo','--single-demo','--timeout','15','--output',str(out/'rule-demo-acceptance.json')],capture_output=True,text=True,timeout=25)
    r['acceptance_rc']=a.returncode;r['acceptance_stdout']=a.stdout[-3000:];r['acceptance_stderr']=a.stderr[-1500:]
    if (out/'rule-demo-acceptance.json').is_file():r['acceptance']=json.loads((out/'rule-demo-acceptance.json').read_text())
except Exception as e:r['error']=type(e).__name__+': '+str(e)
finally:
    server.terminate()
    try:r['owned_server_exit']=server.wait(timeout=8)
    except subprocess.TimeoutExpired:r['server_still_running']=True
    log.close()
    r['server_log']=(out/'server.log').read_text(errors='replace')[-5000:]
    (out/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print('__FRONTEND_'+'BEGIN__',flush=True)
    print(json.dumps(r,ensure_ascii=True),flush=True)
    print('__FRONTEND_'+'END__',flush=True)
