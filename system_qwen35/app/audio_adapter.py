"""App-owned SP_VOICE_V1 client. No recorder/player inside voice worker."""
import json,queue,subprocess,threading,time,uuid,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
VOICE_PYTHON=os.environ.get('SP_VOICE_PYTHON','/home/member-a/voice-a03/venv/bin/python')
class VoiceClient:
    def __init__(self,spool,evidence,endpoint_ms=900,*,asr_threads=2,tts_threads=2,thread_env=None):
        self.spool=Path(spool);self.spool.mkdir(parents=True,exist_ok=True)
        out=Path(evidence);out.mkdir(parents=True,exist_ok=False)
        self.stderr=(out/'stderr.txt').open('x',encoding='utf-8');self.wire=(out/'wire.jsonl').open('x',encoding='utf-8')
        self.events=queue.Queue(maxsize=64);self.pending={};self.mu=threading.RLock();self.dead=False
        self.spawn_begin_ns=time.monotonic_ns()
        self.p=subprocess.Popen([VOICE_PYTHON,'-m','modules.voice_A.worker','--spool',str(self.spool),'--endpoint-ms',str(endpoint_ms),
             '--asr-threads',str(asr_threads),'--tts-threads',str(tts_threads)],
             cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,text=True,encoding='utf-8',bufsize=1,
             env=dict(os.environ,**(thread_env or {})))
        self.reader=threading.Thread(target=self.read,daemon=True);self.reader.start()
        try:self.hello=self.call('hello',timeout=120)
        except BaseException:self.close();raise
        if self.hello.get('type')!='result':self.close();raise RuntimeError('Voice startup failed')
        self.ready_ns=time.monotonic_ns()
    def record(self,x):self.wire.write(json.dumps(x,ensure_ascii=False)+'\n');self.wire.flush()
    def read(self):
        try:
            for line in self.p.stdout:
                r=json.loads(line)
                if r.get('api_version')!=1 or r.get('type') not in ('result','error','event'):raise ValueError('Protocol contamination')
                with self.mu:
                    self.record({'response':r,'received_ns':time.monotonic_ns()})
                    target=self.pending.get((r.get('request_id'),r.get('op')))
                    if target:target.put_nowait(r)
                    else:self.events.put_nowait(r)
        except Exception as exc:
            with self.mu:self.record({'reader_error':str(exc)})
        finally:
            with self.mu:
                self.dead=True
                for q in self.pending.values():
                    if q.empty():q.put_nowait({'type':'error','message':'Voice process exited/protocol error'})
    def begin(self,op,request_id=None,**payload):
        rid=request_id or uuid.uuid4().hex;r=dict(api_version=1,request_id=rid,op=op,**payload);key=(rid,op)
        with self.mu:
            if self.dead or self.p.poll() is not None:raise RuntimeError('Voice unavailable')
            if key in self.pending or len(self.pending)>=8:raise RuntimeError('Application request queue full/duplicate')
            q=queue.Queue(maxsize=1);self.pending[key]=q
            self.record({'request':r,'submitted_ns':time.monotonic_ns()})
            self.p.stdin.write(json.dumps(r,ensure_ascii=False)+'\n');self.p.stdin.flush()
        return key,q
    def finish(self,handle,timeout=60):
        key,q=handle
        try:return q.get(timeout=timeout)
        except queue.Empty:raise TimeoutError('Voice deadline; caller must cancel/reset before reuse')
        finally:
            with self.mu:self.pending.pop(key,None)
    def call(self,op,timeout=60,**payload):return self.finish(self.begin(op,**payload),timeout)
    def close(self):
        if self.p.poll() is None:
            try:self.call('shutdown',timeout=5);self.p.wait(timeout=10)
            except (RuntimeError,TimeoutError,subprocess.TimeoutExpired,BrokenPipeError):self.p.kill();self.p.wait(timeout=5)
        self.reader.join(timeout=2)
        self.record({'closed':True,'exit_code':self.p.returncode});self.stderr.close();self.wire.close()

class HalfDuplex:
    """One turn, explicit stages and epoch. Partial never leaves display buffer."""
    ORDER=('READY','LISTENING','ASR_FINAL','PLANNING','GENERATING','VALIDATING','SYNTHESIZING','PLAYING','READY')
    def __init__(self):self.state='READY';self.epoch=0;self.partial='';self.trace=[];self.played=[];self.mu=threading.RLock()
    def advance(self,state,epoch):
        with self.mu:
            if epoch!=self.epoch:return False
            i=self.ORDER.index(self.state)
            if self.ORDER[i+1]!=state:raise RuntimeError('Illegal half-duplex transition')
            self.state=state;self.trace.append({'state':state,'epoch':epoch,'time_ns':time.monotonic_ns()});return True
    def display_partial(self,text,epoch):
        with self.mu:
            if epoch==self.epoch and self.state=='LISTENING':self.partial=text
    def cancel(self):
        with self.mu:self.epoch+=1;self.state='READY';self.partial='';return self.epoch
