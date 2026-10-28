"""Bounded test client; real subprocess, no simulated graph responses."""
import json,queue,signal,subprocess,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
class Worker:
    def __init__(self,out,scope='all',algorithm='TILED',kernel_threads=4,context=2048,model='Q4_K_M',binary='/home/member-a/qwen35-a05/build-v3/qwen35-s1',physical_ubatch=None):
        self.out=Path(out);self.out.mkdir(parents=True,exist_ok=False)
        self.err=(self.out/'stderr.txt').open('x');self.wire=(self.out/'wire.jsonl').open('x');self.q=queue.Queue(256)
        self.argv=[binary,str(ROOT/f'artifacts/qwen35-0.8b/qwen35-text-{model}.gguf'),'4',str(context),scope,algorithm,str(kernel_threads)]
        if physical_ubatch is not None:self.argv.append(str(physical_ubatch))
        self.p=subprocess.Popen(self.argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
        def read():
            for line in self.p.stdout:self.q.put(json.loads(line))
            self.q.put({'type':'eof'})
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start();self.ready=self.get(120)
        if self.ready['type']!='ready':raise RuntimeError('worker startup failed: '+str(self.ready))
    def get(self,seconds=120):
        v=self.q.get(timeout=seconds);self.wire.write(json.dumps(v,ensure_ascii=False)+'\n');self.wire.flush();return v
    def send(self,v):
        self.wire.write(json.dumps({'request':v},ensure_ascii=False)+'\n');self.wire.flush();self.p.stdin.write(json.dumps(v,ensure_ascii=False)+'\n');self.p.stdin.flush()
    def call(self,req,seconds=180,cancel_at_token=False):
        self.send(req);end=time.monotonic()+seconds;sent=False
        while True:
            r=self.get(max(.001,end-time.monotonic()))
            if r['type']=='token' and cancel_at_token and not sent:self.p.send_signal(signal.SIGUSR1);sent=True
            if r['type'] not in ('token',):return r
    def close(self):
        if self.p.poll() is None:
            try:self.send({'op':'shutdown'})
            except BrokenPipeError:pass # preserve native failure code, don't mask it during cleanup
            try:self.p.wait(timeout=10)
            except subprocess.TimeoutExpired:self.p.kill();self.p.wait(timeout=10)
        self.reader.join(2);self.wire.write(json.dumps({'process_exit_code':self.p.returncode})+'\n');self.wire.close();self.err.close()
