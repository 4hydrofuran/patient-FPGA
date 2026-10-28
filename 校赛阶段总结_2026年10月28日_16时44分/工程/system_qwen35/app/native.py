"""Persistent local A01 C++ worker adapter. No network and no model fallback."""
import hashlib
import json
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time
import math
import os
from jinja2.sandbox import ImmutableSandboxedEnvironment

ROOT=Path(__file__).resolve().parents[2]

class NativeCPU:
    def __init__(self,output,*,binary=Path('/home/member-a/qwen35-a01/native-design-v1/qwen35-cpu'),threads=4,extra_args=(),thread_env=None):
        if type(threads) is not int or not 1<=threads<=16:raise ValueError('CPU threads 1..16 required')
        output=Path(output);output.mkdir(parents=True,exist_ok=False)
        self.err=(output/'stderr.txt').open('x',encoding='utf-8');self.log=(output/'wire.jsonl').open('x',encoding='utf-8')
        self.model=ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'
        self.template=(ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja').read_text(encoding='utf-8')
        self.env=ImmutableSandboxedEnvironment()
        def fail(text):raise ValueError(text)
        self.env.globals['raise_exception']=fail
        self.q=queue.Queue(maxsize=128);self.lock=threading.Lock();self.broken=False;self.count=0;self.trace_context=None
        self.p=subprocess.Popen([str(binary),str(self.model),str(threads),'1024',*map(str,extra_args)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                stderr=self.err,text=True,encoding='utf-8',bufsize=1,env=dict(os.environ,**(thread_env or {})))
        def reader():
            try:
                for line in self.p.stdout:self.q.put(json.loads(line))
            finally:self.q.put({'type':'process_eof'})
        self.reader=threading.Thread(target=reader,daemon=True);self.reader.start()
        try:self.ready=self.q.get(timeout=120)
        except queue.Empty:self.close();raise RuntimeError('Native startup timeout')
        except BaseException:self.close();raise
        self._record(self.ready)
        if self.ready.get('type')!='ready':self.close();raise RuntimeError('Native startup failure')
    def _record(self,x):self.log.write(json.dumps(x,ensure_ascii=False)+'\n');self.log.flush()
    def generate(self,messages,timeout_s=20):
        if type(timeout_s) not in (int,float) or not math.isfinite(timeout_s) or timeout_s<=0:raise ValueError('Positive finite deadline required')
        if not self.lock.acquire(blocking=False):raise RuntimeError('Native busy')
        try:
            if self.broken or self.p.poll() is not None:raise RuntimeError('Native unavailable; explicit restart required')
            prompt=self.env.from_string(self.template).render(messages=messages,add_generation_prompt=True,enable_thinking=False)
            if not prompt.endswith('<think>\n\n</think>\n\n'):raise RuntimeError('Non-thinking template mismatch')
            self.count+=1;rid='a02-'+str(self.count)
            if self.trace_context:rid=self.trace_context['session_id']+':'+self.trace_context['request_id']
            req={'id':rid,'prompt':prompt,'max_tokens':64,'logits_mode':'final'}
            if self.trace_context:req.update(session_id=self.trace_context['session_id'],session_epoch=self.trace_context['epoch'])
            self._record({'request':req});start=time.monotonic()
            self.p.stdin.write(json.dumps(req,ensure_ascii=False)+'\n');self.p.stdin.flush()
            while True:
                try:r=self.q.get(timeout=max(0,timeout_s-(time.monotonic()-start)))
                except queue.Empty:
                    self.broken=True
                    if self.p.poll() is None:self.p.send_signal(signal.SIGUSR1)
                    self._record({'event':'deadline','request_id':rid,'deadline_s':timeout_s,'cancel_signal':'SIGUSR1'})
                    raise TimeoutError('Actual local worker deadline exceeded; worker quarantined until close')
                self._record(r)
                if r.get('type')=='process_eof':self.broken=True;raise RuntimeError('Native exited')
                if r.get('id')!=rid:raise RuntimeError('Response identity mismatch')
                if r['type']=='error':raise RuntimeError(r['message'])
                if r['type']=='result':
                    r['round_wall_ms']=(time.monotonic()-start)*1000
                    r['actual_backend']='CPU_REFERENCE';return r
        except TimeoutError:
            # TimeoutError subclasses OSError. Keep real deadlines distinct from
            # transport failure for explicit TIMEOUT provenance at the app gate.
            raise
        except OSError as exc:
            self.broken=True
            raise RuntimeError('Native transport failed; explicit restart required') from exc
        finally:self.lock.release()
    def close(self):
        if self.p.poll() is None:
            try:self.p.stdin.write('{"op":"shutdown"}\n');self.p.stdin.flush();self.p.wait(timeout=3)
            except (subprocess.TimeoutExpired,BrokenPipeError):self.p.kill();self.p.wait(timeout=3)
        self.reader.join(timeout=2)
        while not self.q.empty():self._record(self.q.get_nowait())
        self._record({'event':'closed','exit_code':self.p.returncode,'quarantined':self.broken})
        self.err.close();self.log.close()
