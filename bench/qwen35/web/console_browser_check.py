"""Exercise the derived console in local headless Edge with explicit HTTP/SSE fixtures."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import sys
import urllib.request
import urllib.parse

ROOT=Path(__file__).resolve().parents[3]
STATIC=ROOT/'platform/qwen35/web/vendor/web_gateway/src/patient_web/static'

SETUP=r'''
window.fixture={gets:0,posts:0,next:1,session:null,events:[],accepted:[],epoch:0};
const fixture=window.fixture;
const clone=value=>JSON.parse(JSON.stringify(value));
function snapshot(){ return {session_id:fixture.session,instance_id:"instance",cursor:fixture.seq||0,
  case_id:"SYN_CP_01",epoch:fixture.epoch,phase:fixture.closed?"FINISHED":fixture.busy?"GENERATING":"READY",
  closed:!!fixture.closed,active_request_id:fixture.busy||null,turns:clone(fixture.turns||[])}; }
window.fetch=async (path,options={})=>{
  const body=options.body?JSON.parse(options.body):null; let data;
  if(path==="/ui/v1/status") data={ready:true,instance_id:"instance",current_session_id:fixture.session,
    phase:"READY",backend:{configured:"managed-pl",execution_kind:"FPGA_REAL"},capabilities:{cancel_turn:false}};
  else if(path==="/ui/v1/cases")data={cases:[{case_id:"SYN_CP_01",title:"合成病例"}]};
  else if(path==="/ui/v1/sessions"){
    fixture.session="session"+fixture.next++;fixture.turns=[];fixture.busy=null;fixture.closed=false;fixture.seq=(fixture.seq||0)+1;fixture.epoch=0;
    data={session_id:fixture.session};
  } else if(path.endsWith("/turns")){
    fixture.posts++;fixture.accepted.push(clone(body));fixture.busy=body.request_id;fixture.seq++;
    fixture.turns.push({request_id:body.request_id,question:body.text,status:"RUNNING",answer:null});data={status:"accepted"};
  } else if(path.endsWith("/finish")) { fixture.closed=true;fixture.seq++;data={status:"finished"}; }
  else if(path.endsWith("/evaluation"))data={evaluation_id:"eval-"+fixture.session,session_id:fixture.session,
    rule_score:{score:10,max_score:100},covered_topics:[],missing_topics:[],case_id:"SYN_CP_01",frozen_turn_count:1,
    summary_text:"评价",disclaimer:"合成病例",scoring_note:"话题覆盖",topics:[],review_items:[]};
  else { fixture.gets++;data=snapshot(); }
  return {ok:true,json:async()=>clone(data)};
};
window.EventSource=class {
  constructor(){this.listeners={};fixture.events.push(this);setTimeout(()=>this.onopen?.(),0);}
  addEventListener(name,fn){this.listeners[name]=fn;}
  close(){this.closed=true;}
  emit(name,extra={}){
    this.listeners[name]?.({data:JSON.stringify({event:name,seq:++fixture.seq,session_id:fixture.session,
      instance_id:"instance",request_id:fixture.busy,epoch:fixture.epoch,data:{},...extra})});
  }
};
'''

CHECK=r'''
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const checks=[];
function check(value,name){if(!value)throw new Error(name);checks.push(name);}
async function exercise(){
  await delay(100);document.getElementById("start").click();await delay(100);
  check(!!fixture.session,"session initialized");
  const input=document.getElementById("question"),form=document.getElementById("question-form");
  input.value="每次疼痛持续多久？";
  input.dispatchEvent(new CompositionEvent("compositionstart"));
  const key=new KeyboardEvent("keydown",{key:"Enter",isComposing:true,bubbles:true,cancelable:true});
  input.dispatchEvent(key);form.dispatchEvent(new SubmitEvent("submit",{cancelable:true}));await delay(20);
  check(key.defaultPrevented && fixture.posts===0,"IME candidate Enter does not submit");
  input.dispatchEvent(new CompositionEvent("compositionend"));await delay(60);
  form.dispatchEvent(new SubmitEvent("submit",{cancelable:true}));
  form.dispatchEvent(new SubmitEvent("submit",{cancelable:true}));await delay(100);
  check(fixture.posts===1,"explicit submit generates exactly one request");
  const stream=fixture.events.at(-1),rid=fixture.busy;
  let before=fixture.gets;
  stream.emit("generation.started");stream.emit("validation.started");await delay(80);
  check(fixture.gets-before<=1,"adjacent events share one snapshot GET");
  const answer="每次疼痛持续10分钟。";
  fixture.turns[0]={...fixture.turns[0],answer,answer_source:"MODEL",actual_backend:"FPGA_REAL",status:"COMPLETED"};
  stream.emit("answer.ready",{request_id:rid,data:{text:answer,answer_source:"MODEL",actual_backend:"FPGA_REAL"}});
  fixture.busy=null;stream.emit("turn.completed",{request_id:rid});await delay(150);
  check(document.getElementById("turns").textContent.includes(answer),"checked SSE answer reaches DOM");
  const timing=window.patientResponseTimings()[0];
  check(timing.request_id===rid && timing.answer_ready_ms>=timing.submitted_ms,"browser answer.ready timing uses request ID");
  // Virtual-time timers can run ahead of compositor frames; await the actual frames.
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  const painted=window.patientResponseTimings()[0];
  check(painted.painted_ms>=painted.answer_ready_ms && painted.answer_source==="MODEL","browser observes checked DOM after animation frames");
  const oldNode=document.getElementById("turns").firstElementChild;
  before=fixture.gets;stream.emit("session.snapshot",{data:snapshot()});await delay(80);
  check(fixture.gets===before,"snapshot event does not issue duplicate GET");
  check(document.getElementById("turns").firstElementChild===oldNode,"unchanged turn DOM is retained");
  fixture.epoch=1;stream.emit("session.snapshot",{data:snapshot()});await delay(30);
  stream.emit("answer.ready",{request_id:rid,epoch:0,data:{text:"stale"}});await delay(50);
  check(!document.getElementById("turns").textContent.includes("stale"),"old epoch result is ignored");
  before=fixture.gets;await poll();check(fixture.gets===before,"healthy SSE avoids periodic full snapshot refresh");
  stream.onerror();before=fixture.gets;await poll();check(fixture.gets>before,"disconnected SSE retains polling fallback");
  document.getElementById("finish").click();await delay(100);
  check(!document.getElementById("evaluation-result").hidden,"finish renders frozen evaluation");
  document.getElementById("new-session").click();await delay(100);
  check(fixture.session==="session2" && !document.getElementById("turns").textContent,"new session clears current transcript");
  stream.emit("answer.ready",{session_id:"session1",request_id:rid,data:{text:"foreign"}});await delay(50);
  check(!document.getElementById("turns").textContent.includes("foreign"),"old connection/session result is ignored");
  return {status:"PASS_BROWSER_FIXTURES",checks,timing:painted,posts:fixture.posts,BOARD:"NOT_TESTED",model_executed:false};
}
exercise().then(result=>{
  const p=document.createElement("pre");p.id="test-result";p.textContent=JSON.stringify(result);document.body.append(p);
}).catch(error=>{
  const p=document.createElement("pre");p.id="test-result";p.textContent=JSON.stringify({status:"FAILED_BROWSER_FIXTURES",error:String(error),checks});document.body.append(p);
});
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--edge',type=Path,default=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'))
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    # Inline the exact console source into a local fixture page; no live service/board.
    html=STATIC.joinpath('index.html').read_text(encoding='utf-8')
    html=html.replace('<script src="/console.js" defer></script>',
        '<script>'+SETUP+'</script><script>'+STATIC.joinpath('console.js').read_text(encoding='utf-8')+'</script><script>'+CHECK+'</script>')
    page=a.output/'fixture.html';page.write_text(html,encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='a12-fast-browser-') as profile:
        command=[str(a.edge),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
            '--user-data-dir='+profile,'--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',page.resolve().as_uri()]
        startup=None
        if hasattr(subprocess,'STARTUPINFO'):
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        begin=time.monotonic();connection=None;result=dict(status='FAILED_NO_BROWSER_RESULT')
        with (a.output/'stderr.txt').open('wb') as log:
            process=subprocess.Popen(command,stdout=log,stderr=log,startupinfo=startup)
            try:
                deadline=time.monotonic()+20
                port_file=Path(profile)/'DevToolsActivePort'
                port=None
                while time.monotonic()<deadline:
                    try:port=int(port_file.read_text().splitlines()[0]);break
                    except (FileNotFoundError,PermissionError,IndexError,ValueError):time.sleep(.05)
                if port is None:raise TimeoutError('Edge debugging port not ready')
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list',timeout=5) as response:
                    target=next(t for t in json.load(response) if t['type']=='page')
                sys.path.insert(0,str(ROOT/'platform/qwen35/web'))
                from browser_bidi import Bidi
                import socket,base64,os
                class CDP(Bidi):
                    def __init__(self,url):
                        u=urllib.parse.urlsplit(url);self.s=socket.create_connection((u.hostname,u.port),timeout=5);self.i=0
                        key=base64.b64encode(os.urandom(16)).decode()
                        self.s.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
                        head=b''
                        while not head.endswith(b'\r\n\r\n'):head+=self.exact(1)
                        if b' 101 ' not in head:raise RuntimeError('local CDP handshake failed')
                connection=CDP(target['webSocketDebuggerUrl'])
                while time.monotonic()<deadline:
                    value=connection.call('Runtime.evaluate',dict(expression="document.getElementById('test-result')?.textContent",returnByValue=True))
                    text=value.get('result',{}).get('value')
                    if text:result=json.loads(text);break
                    time.sleep(.1)
                dom=connection.call('Runtime.evaluate',dict(expression='document.documentElement.outerHTML',returnByValue=True))
                (a.output/'dom.html').write_text(dom['result']['value'],encoding='utf-8')
                connection.call('Browser.close',{})
                process.wait(timeout=10)
            finally:
                if connection:connection.s.close()
                if process.poll() is None:process.terminate();process.wait(timeout=5)
    result.update(browser_exit=process.returncode,elapsed_s=time.monotonic()-begin)
    (a.output/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['status']=='PASS_BROWSER_FIXTURES' and process.returncode==0 else 1)


if __name__=='__main__':main()
