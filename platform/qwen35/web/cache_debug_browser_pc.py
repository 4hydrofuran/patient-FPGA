"""Actual Edge hit/miss display and next-session control, CPU runtime only."""
import base64,json,subprocess,tempfile,time,urllib.request
from pathlib import Path
from answer_cache_browser import CDP

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/frontend_board_A/20261027-cache-debug-v1/pc-browser'
OUT.mkdir(parents=True,exist_ok=False);rows=[]
with tempfile.TemporaryDirectory(prefix='cache-debug-') as profile:
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    with (OUT/'edge.log').open('wb') as log:
        process=subprocess.Popen(['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','--headless','--disable-gpu',
            '--no-first-run','--no-default-browser-check','--user-data-dir='+profile,'--remote-debugging-port=0','http://127.0.0.1:18783/'],
            stdout=log,stderr=log,startupinfo=startup)
        ws=None
        try:
            file=Path(profile)/'DevToolsActivePort';end=time.monotonic()+20
            while not file.exists() and time.monotonic()<end:time.sleep(.05)
            port=int(file.read_text().splitlines()[0])
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list') as f:tab=next(t for t in json.load(f) if t['type']=='page')
            ws=CDP(tab['webSocketDebuggerUrl'])
            ws.wait("typeof service!=='undefined' && service?.ready && !document.getElementById('start').disabled")
            ws.evaluate("document.getElementById('cache-debug-settings').open=true;document.getElementById('next-cache-mode').value='hit';document.getElementById('start').click()")
            ws.wait("current && current.cache_mode==='hit' && !document.getElementById('send').disabled")
            sid=ws.evaluate('current.session_id')
            def ask():
                count=ws.evaluate('patientResponseTimings().length')
                ws.evaluate("document.getElementById('question').value='疼痛在什么位置？';document.getElementById('question-form').requestSubmit()")
                timing=ws.wait(f"(()=>{{let t=patientResponseTimings();return t.length>{count} && t.at(-1).painted_ms!==undefined && !current.active_request_id ? t.at(-1):null}})()")
                return ws.evaluate("fetch('/ui/v1/sessions/'+current.session_id+'/turns/'+"+json.dumps(timing['request_id'])+").then(r=>r.json())")
            hit=ask();assert hit['answer_source']=='MODEL_CACHE' and hit['execution_mode']=='CPU' and not hit['delivery_receipt']['model_called']
            badge=ws.evaluate("document.querySelector('#turns .answer-cache-source').textContent")
            assert badge=='CPU 模式 · 缓存命中' and '已核验' not in badge
            (OUT/'hit.png').write_bytes(base64.b64decode(ws.call('Page.captureScreenshot',dict(format='png'))['data']))
            ws.evaluate("document.getElementById('next-cache-mode').value='miss';document.getElementById('next-cache-mode').dispatchEvent(new Event('change'))")
            ws.call('Page.reload',{})
            ws.wait("typeof current!=='undefined' && current?.session_id==="+json.dumps(sid)+" && !document.getElementById('send').disabled")
            assert ws.evaluate('current.cache_mode')=='hit'
            assert ws.evaluate("document.getElementById('next-cache-mode').value")=='miss'
            still_hit=ask();assert still_hit['answer_source']=='MODEL_CACHE'
            ws.evaluate("document.getElementById('finish').click()")
            ws.wait("current.closed && !document.getElementById('new-session').disabled")
            ws.evaluate("document.getElementById('new-session').click()")
            ws.wait("!current.closed && current.cache_mode==='miss' && !document.getElementById('send').disabled")
            miss=ask();assert miss['answer_source']=='MODEL' and miss['actual_backend']=='CPU_REFERENCE' and miss['delivery_receipt']['model_called']
            note=ws.evaluate("document.querySelector('#turns .turn-backend').textContent")
            assert note=='CPU' and ws.evaluate("document.querySelectorAll('#turns .answer-cache-source').length")==0
            (OUT/'miss.png').write_bytes(base64.b64decode(ws.call('Page.captureScreenshot',dict(format='png'))['data']))
            rows=[dict(kind='hit',badge=badge,turn=hit),dict(kind='current_still_hit_after_next_mode_change',turn=still_hit),dict(kind='next_miss',note=note,turn=miss)]
            ws.call('Browser.close',{});process.wait(10)
        finally:
            if ws:ws.s.close()
            if process.poll() is None:process.terminate();process.wait(10)
report=dict(status='PASS_REAL_CPU_HIT_MISS_DISPLAY_NEXT_SESSION_AND_REFRESH',rows=rows,browser_exit=process.returncode,BOARD='NOT_TESTED')
(OUT/'RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=report['status'],badge=rows[0]['badge'],miss_note=rows[-1]['note'],actual_cpu_model_calls=1),ensure_ascii=False))
