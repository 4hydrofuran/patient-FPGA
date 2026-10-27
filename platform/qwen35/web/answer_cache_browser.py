"""Real local Edge browser measurements against an actual HTTP/model/cache service."""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from browser_bidi import Bidi
from answer_cache_paths import default_parent


class CDP(Bidi):
    def __init__(self,url):
        u=urllib.parse.urlsplit(url);self.s=socket.create_connection((u.hostname,u.port),timeout=15);self.i=0
        key=base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        head=b''
        while not head.endswith(b'\r\n\r\n'):head+=self.exact(1)
        if b' 101 ' not in head:raise RuntimeError('CDP handshake failed')

    def evaluate(self,expression):
        result=self.call('Runtime.evaluate',dict(expression=expression,returnByValue=True,awaitPromise=True))
        if 'exceptionDetails' in result:raise RuntimeError(str(result['exceptionDetails']))
        return result.get('result',{}).get('value')

    def wait(self,expression,timeout=180):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            value=self.evaluate(expression)
            if value:return value
            time.sleep(.02)
        raise TimeoutError('browser condition: '+expression)


def measure(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rows=json.loads(a.cohort.read_text(encoding='utf-8'))['real_inputs'];results=[]
    if a.limit:rows=rows[:a.limit]
    with tempfile.TemporaryDirectory(prefix='a12-real-response-') as profile:
        command=[str(a.edge),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
            '--user-data-dir='+profile,'--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',a.url]
        startup=None
        if hasattr(subprocess,'STARTUPINFO'):
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        connection=None
        with (out/'edge-stderr.txt').open('wb') as log:
            process=subprocess.Popen(command,stdout=log,stderr=log,startupinfo=startup)
            try:
                file=Path(profile)/'DevToolsActivePort';end=time.monotonic()+15;port=None
                while time.monotonic()<end:
                    try:port=int(file.read_text().splitlines()[0]);break
                    except (FileNotFoundError,PermissionError,IndexError,ValueError):time.sleep(.05)
                if port is None:raise TimeoutError('Edge debugging port not ready')
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list',timeout=5) as response:
                    target=next(t for t in json.load(response) if t['type']=='page')
                connection=CDP(target['webSocketDebuggerUrl'])
                connection.wait("typeof service !== 'undefined' && service?.ready && document.getElementById('cases').options.length")
                active=None
                for row in rows:
                    item=row['application'];cid=item['case_id']
                    if active!=cid:
                        if active:
                            connection.evaluate("document.getElementById('finish').click()")
                            connection.wait("current?.closed && !document.getElementById('evaluation-result').hidden")
                        connection.evaluate("document.getElementById('cases').value="+json.dumps(cid)+";document.getElementById('start').click()")
                        connection.wait("current?.case_id==="+json.dumps(cid)+" && !current.closed && !document.getElementById('send').disabled")
                        active=cid
                    before=connection.evaluate('patientResponseTimings().length')
                    connection.evaluate("document.getElementById('question').value="+json.dumps(item['question'])+";document.getElementById('question-form').requestSubmit()")
                    timing=connection.wait(f"(()=>{{const a=patientResponseTimings();return a.length>{before} && a.at(-1).painted_ms!==undefined && !current.active_request_id ? a.at(-1):null}})()")
                    rid=timing['request_id']
                    turn=connection.evaluate("fetch('/ui/v1/sessions/'+current.session_id+'/turns/'+"+json.dumps(rid)+").then(r=>{if(!r.ok)throw Error(r.status);return r.json()})")
                    expected='MODEL_CACHE' if a.mode=='cache' else 'MODEL'
                    if turn['answer_source']!=expected or turn['status']!='COMPLETED':raise RuntimeError('unexpected actual turn: '+str(turn))
                    if timing['visibility_state']!='visible':raise RuntimeError('browser was not visible to its compositor')
                    if a.mode=='cache' and (turn['actual_backend'] is not None or turn['delivery_receipt']['model_called'] is not False):
                        raise RuntimeError('cached answer mislabels current inference')
                    result=dict(id=row['id'],case_id=cid,question=item['question'],answer=turn['answer'],
                        timing=timing,turn=turn,measured_with='REAL_EDGE_REAL_HTTP_SSE',BOARD='NOT_TESTED')
                    results.append(result)
                    (out/(row['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    if len(results)==1:
                        capture=connection.call('Page.captureScreenshot',dict(format='png'))
                        (out/'first-answer.png').write_bytes(base64.b64decode(capture['data']))
                        if a.mode=='cache' and not connection.evaluate("!!document.querySelector('.answer-cache-source')"):
                            raise RuntimeError('cache origin badge missing')
                    print(json.dumps(dict(id=row['id'],source=turn['answer_source'],submit_to_paint_ms=timing['submit_to_paint_ms'])),flush=True)
                connection.evaluate("document.getElementById('finish').click()")
                connection.wait("current?.closed && !document.getElementById('evaluation-result').hidden")
                connection.call('Browser.close',{});process.wait(timeout=10)
            finally:
                if connection:connection.s.close()
                if process.poll() is None:process.terminate();process.wait(timeout=5)
    summary=dict(status='PASS_REAL_BROWSER_RESPONSES',mode=a.mode,questions=len(results),rows=results,
                 browser_exit=process.returncode,BOARD='NOT_TESTED',clock='browser performance.now')
    (out/'RESULT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=('live','cache'),required=True)
    p.add_argument('--url',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--limit',type=int)
    p.add_argument('--cohort',type=Path,default=default_parent()/'COHORT.json')
    p.add_argument('--edge',type=Path,default=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'))
    r=measure(p.parse_args());print(json.dumps({k:v for k,v in r.items() if k!='rows'},indent=2))
