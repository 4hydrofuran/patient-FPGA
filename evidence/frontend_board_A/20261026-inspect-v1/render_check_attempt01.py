import json,subprocess,time,socket,urllib.request,hashlib
from pathlib import Path
base=Path('/home/ubuntu/patient-web-demo-20261026')
out=base/'inspection-20261026-v1'
shot=Path.home()/'snap/firefox/common/frontend-check-20261026-v1'
(shot/'profile').mkdir(exist_ok=False)
r={'scope':'BOARD_FIREFOX_RENDER_ONLY_RULE_DEMO','profile_fix':'create missing explicit profile directory'}
s=socket.socket();s.bind(('127.0.0.1',8000));s.close()
log=(out/'render-server.log').open('xb')
server=subprocess.Popen([str(base/'start-demo.sh')],stdout=log,stderr=subprocess.STDOUT)
r['owned_server_pid']=server.pid
try:
    for i in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=1) as f:r['status']=json.load(f)
            break
        except OSError:time.sleep(.25)
    else:raise RuntimeError('Demo readiness timeout')
    with (out/'render-firefox.out').open('xb') as bo,(out/'render-firefox.err').open('xb') as be:
        p=subprocess.Popen(['/snap/bin/firefox','--headless','--no-remote','--profile',str(shot/'profile'),'--window-size','1024,600','--screenshot',str(shot/'home.png'),'http://127.0.0.1:8000/'],stdout=bo,stderr=be)
        r['owned_browser_pid']=p.pid
        try:r['firefox_rc']=p.wait(timeout=55)
        except subprocess.TimeoutExpired:
            r['timeout']=True;p.terminate()
            try:r['firefox_rc']=p.wait(timeout=8)
            except subprocess.TimeoutExpired:r['browser_still_running']=True
    r['firefox_stdout']=(out/'render-firefox.out').read_text(errors='replace')[-2500:]
    r['firefox_stderr']=(out/'render-firefox.err').read_text(errors='replace')[-5000:]
    if (shot/'home.png').is_file():
        raw=(shot/'home.png').read_bytes();r.update(screenshot_path=str(shot/'home.png'),screenshot_bytes=len(raw),screenshot_sha256=hashlib.sha256(raw).hexdigest())
except Exception as e:r['error']=type(e).__name__+': '+str(e)
finally:
    server.terminate()
    try:r['owned_server_exit']=server.wait(timeout=8)
    except subprocess.TimeoutExpired:r['server_still_running']=True
    log.close();r['server_log']=(out/'render-server.log').read_text(errors='replace')[-6000:]
    (out/'render-result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print('__FRONTEND_'+'BEGIN__',flush=True)
    print(json.dumps(r,ensure_ascii=True),flush=True)
    print('__FRONTEND_'+'END__',flush=True)
