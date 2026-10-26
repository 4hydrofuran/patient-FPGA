import os,json,socket,struct,base64,hashlib,time,subprocess,urllib.request
from pathlib import Path
class Bidi:
    def __init__(self):
        self.s=socket.create_connection(('127.0.0.1',9222),timeout=12);self.i=0
        key=base64.b64encode(os.urandom(16)).decode()
        request='GET /session HTTP/1.1\r\nHost: 127.0.0.1:9222\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\n\r\n'
        self.s.sendall(request.encode());head=b''
        while not head.endswith(b'\r\n\r\n'):head+=self.exact(1)
        if b' 101 ' not in head:raise RuntimeError('WebSocket upgrade failed: '+head.decode())
    def exact(self,n):
        data=b''
        while len(data)<n:
            p=self.s.recv(n-len(data))
            if not p:raise EOFError('Browser connection closed')
            data+=p
        return data
    def send(self,payload,opcode=1):
        key=os.urandom(4);n=len(payload)
        head=bytes([128|opcode,128|n]) if n<126 else bytes([128|opcode,128|126])+struct.pack('!H',n) if n<65536 else bytes([128|opcode,128|127])+struct.pack('!Q',n)
        self.s.sendall(head+key+bytes(x^key[i%4] for i,x in enumerate(payload)))
    def receive(self):
        parts=[]
        while True:
            a,b=self.exact(2);n=b&127
            if n==126:n=struct.unpack('!H',self.exact(2))[0]
            elif n==127:n=struct.unpack('!Q',self.exact(8))[0]
            mask=self.exact(4) if b&128 else None;p=self.exact(n)
            if mask:p=bytes(x^mask[i%4] for i,x in enumerate(p))
            op=a&15
            if op==8:raise EOFError('WebSocket close')
            if op==9:self.send(p,10);continue
            parts.append(p)
            if a&128:return json.loads(b''.join(parts))
    def call(self,method,params):
        self.i+=1;self.send(json.dumps(dict(id=self.i,method=method,params=params)).encode())
        while True:
            r=self.receive()
            if r.get('id')!=self.i:continue
            if r.get('type')=='error':raise RuntimeError(json.dumps(r))
            return r['result']
b=Path('/home/ubuntu/patient-web-demo-20261026');out=b/'inspection-20261026-v1'
shots=Path.home()/'snap/firefox/common/frontend-check-20261026-v1'
profile=shots/'interactive-profile';profile.mkdir(exist_ok=False)
r={'scope':'ACTUAL_BOARD_FIREFOX_DOM_AND_SSE_RULE_DEMO_ONLY','screenshots':{}}
server=None;browser=None;ws=None
try:
    for port in (8000,9222):
        with socket.socket() as s:s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',port))
    log=(out/'interactive-server.log').open('xb')
    server=subprocess.Popen([str(b/'start-demo.sh')],stdout=log,stderr=subprocess.STDOUT);r['server_pid']=server.pid
    for i in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=1) as f:r['initial_status']=json.load(f)
            break
        except OSError:time.sleep(.25)
    else:raise RuntimeError('Service startup timeout')
    blog=(out/'interactive-firefox.log').open('xb')
    browser=subprocess.Popen(['/snap/bin/firefox','--headless','--no-remote','--profile',str(profile),'--remote-debugging-port','9222','about:blank'],stdout=blog,stderr=subprocess.STDOUT);r['browser_pid']=browser.pid
    for i in range(100):
        try:ws=Bidi();break
        except ConnectionRefusedError:time.sleep(.25)
    else:raise RuntimeError('Browser startup timeout')
    caps=ws.call('session.new',{'capabilities':{}});r['browser_version']=caps['capabilities'].get('browserVersion')
    context=ws.call('browsingContext.create',{'type':'tab'})['context']
    ws.call('browsingContext.setViewport',{'context':context,'viewport':{'width':1024,'height':600},'devicePixelRatio':1})
    ws.call('browsingContext.navigate',{'context':context,'url':'http://127.0.0.1:8000/','wait':'complete'})
    def evaluate(code):
        result=ws.call('script.evaluate',{'expression':code,'target':{'context':context},'awaitPromise':True})
        if result.get('type')=='exception':raise RuntimeError(json.dumps(result))
        return result.get('result',{}).get('value')
    def await_true(condition):
        expression='(async()=>{for(let i=0;i<60;i++){if('+condition+')return true;await new Promise(r=>setTimeout(r,100));}return false;})()'
        if evaluate(expression) is not True:raise RuntimeError('DOM condition timeout: '+condition)
    def screenshot(name):
        image=base64.b64decode(ws.call('browsingContext.captureScreenshot',{'context':context})['data'])
        (shots/name).write_bytes(image);r['screenshots'][name]={'bytes':len(image),'sha256':hashlib.sha256(image).hexdigest()}
    await_true("document.getElementById('cases').options.length===3 && !document.getElementById('start').disabled")
    r['ready_dom']=json.loads(evaluate("JSON.stringify({cases:document.getElementById('cases').options.length,startEnabled:!document.getElementById('start').disabled,state:document.getElementById('state').textContent})"))
    screenshot('ready.png')
    evaluate("document.getElementById('start').click();true")
    await_true("!document.getElementById('question').disabled")
    question='\u6bcf\u6b21\u75bc\u75db\u6301\u7eed\u591a\u4e45\uff1f'
    evaluate("document.getElementById('question').value="+json.dumps(question)+";document.getElementById('question-form').requestSubmit();true")
    await_true("document.getElementById('turns').textContent.includes('10') && !document.getElementById('finish').disabled")
    r['answer_dom']=evaluate("document.getElementById('turns').textContent")
    screenshot('answered.png')
    evaluate("document.getElementById('finish').click();true")
    await_true("!document.getElementById('evaluation-result').hidden && document.getElementById('total-score').textContent==='10'")
    r['evaluation_dom']=json.loads(evaluate("JSON.stringify({score:document.getElementById('total-score').textContent,summary:document.getElementById('summary-text').textContent,error:document.getElementById('error').textContent})"))
    screenshot('evaluation.png');r['verdict']='PASS_BOARD_FIREFOX_RULE_WORKFLOW'
    try:ws.call('browser.close',{})
    except EOFError:pass
except Exception as e:r['error']=type(e).__name__+': '+str(e)
finally:
    if ws:ws.s.close()
    for name,p in [('browser',browser),('server',server)]:
        if p:
            if p.poll() is None:p.terminate()
            try:r[name+'_exit']=p.wait(timeout=8)
            except subprocess.TimeoutExpired:r[name+'_still_running']=True
    for name in ('interactive-firefox.log','interactive-server.log'):
        p=out/name
        if p.exists():r[name]=p.read_text(errors='replace')[-5000:]
    (out/'interactive-result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print('__FRONTEND_'+'BEGIN__',flush=True)
    print(json.dumps(r,ensure_ascii=True),flush=True)
    print('__FRONTEND_'+'END__',flush=True)
