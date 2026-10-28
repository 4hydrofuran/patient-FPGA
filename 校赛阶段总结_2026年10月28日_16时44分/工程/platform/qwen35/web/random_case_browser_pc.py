"""Three real Edge random-case sessions against the local cached model service."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
from answer_cache_browser import CDP


def run(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);rows=[]
    edge='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
    with tempfile.TemporaryDirectory(prefix='case20-random-') as profile:
        start=subprocess.STARTUPINFO();start.dwFlags|=subprocess.STARTF_USESHOWWINDOW;start.wShowWindow=0
        with (out/'edge.log').open('wb') as log:
            process=subprocess.Popen([edge,'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--user-data-dir='+profile,'--remote-debugging-port=0',a.url],stdout=log,stderr=log,startupinfo=start)
            ws=None
            try:
                portfile=Path(profile)/'DevToolsActivePort'
                end=time.monotonic()+20
                while not portfile.exists() and time.monotonic()<end:time.sleep(.05)
                port=int(portfile.read_text().splitlines()[0])
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list') as f:tab=next(t for t in json.load(f) if t['type']=='page')
                ws=CDP(tab['webSocketDebuggerUrl'])
                ws.wait("typeof service!=='undefined' && service?.ready && !document.getElementById('start').disabled")
                assert ws.evaluate("document.getElementById('cases')===null")
                assert ws.evaluate('service.capabilities.case_count')==20
                for i in range(3):
                    ws.evaluate("document.getElementById('start').click()" if i==0 else "document.getElementById('new-session').click()")
                    ws.wait("current && !current.closed && !document.getElementById('send').disabled")
                    sid=ws.evaluate('current.session_id');cid=ws.evaluate('current.case_id')
                    if i==0:
                        ws.call('Page.reload',{})
                        ws.wait("typeof current!=='undefined' && current?.session_id==="+json.dumps(sid)+" && !document.getElementById('send').disabled")
                        assert ws.evaluate('current.case_id')==cid
                    before=ws.evaluate('patientResponseTimings().length')
                    ws.evaluate("document.getElementById('question').value='疼痛在什么位置？';document.getElementById('question-form').requestSubmit()")
                    timing=ws.wait(f"(()=>{{const t=patientResponseTimings();return t.length>{before} && t.at(-1).painted_ms!==undefined && !current.active_request_id ? t.at(-1):null}})()")
                    turn=ws.evaluate("fetch('/ui/v1/sessions/'+current.session_id+'/turns/'+"+json.dumps(timing['request_id'])+").then(r=>r.json())")
                    assert turn['answer_source']=='MODEL_CACHE' and turn['delivery_receipt']['model_called'] is False
                    rows.append(dict(session_id=sid,case_id=cid,text=turn['answer'],timing=timing))
                    if i==0:(out/'random-answer.png').write_bytes(base64.b64decode(ws.call('Page.captureScreenshot',dict(format='png'))['data']))
                    ws.evaluate("document.getElementById('finish').click()")
                    ws.wait("current.closed && !document.getElementById('evaluation-result').hidden")
                ws.call('Browser.close',{});process.wait(10)
            finally:
                if ws:ws.s.close()
                if process.poll() is None:process.terminate();process.wait(10)
    report=dict(status='PASS_RANDOM_BROWSER_REFRESH_ANSWER_FINISH_REDRAW',rows=rows,pool_size=20,manual_selector=False,
        native_calls_for_cached_answers=0,browser_exit=process.returncode,BOARD='NOT_TESTED')
    (out/'RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--output',type=Path,required=True);run(p.parse_args())
