"""Bounded persistent JSONL service, serial inference and immediate control path."""
import argparse,hashlib,json,os,queue,re,sys,threading,time,uuid
from pathlib import Path,PurePosixPath

class Spool:
    MAX_BYTES=64*1024*1024
    MAX_FILES=512
    def __init__(self,path):
        p=Path(path)
        if p.is_symlink():raise ValueError('Spool link')
        p.mkdir(mode=0o700,parents=True,exist_ok=True);self.root=p.resolve()
    def path(self,name,session):
        if not isinstance(name,str) or '\\' in name or ':' in name:raise ValueError('Invalid spool path')
        p=PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!=session:raise ValueError('Foreign/traversal spool path')
        target=self.root.joinpath(*p.parts)
        for x in (target,*target.parents):
            if x==self.root:break
            if x.is_symlink():raise ValueError('Spool symlink')
        if not target.resolve().is_relative_to(self.root):raise ValueError('Spool escape')
        return target
    def budget(self,reserve=0):
        total=0;count=0
        for p in self.root.rglob('*'):
            if p.is_symlink():raise ValueError('Spool contains symlink')
            if p.is_file():count+=1;total+=p.stat().st_size
        if count>=self.MAX_FILES or total+reserve>self.MAX_BYTES:raise ValueError('Spool quota exceeded')

class Worker:
    def __init__(self,spool,emit,engine):
        self.spool=Spool(spool);self.emit=emit;self.engine=engine
        self.q=queue.Queue(maxsize=4);self.mu=threading.RLock();self.jobs={};self.epochs={};self.streams={};self.generated={}
        self.seen=set();self.stopping=False;self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def send(self,r,kind='result',**data):self.emit(dict(api_version=1,request_id=r.get('request_id'),op=r.get('op'),type=kind,**data))
    def submit(self,r):
        if not isinstance(r,dict) or r.get('api_version')!=1 or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(r.get('request_id',''))):raise ValueError('Invalid envelope')
        op=r.get('op');sid=r.get('session_id','default')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',str(sid)):raise ValueError('Invalid session')
        with self.mu:
            if op=='hello':
                self.send(r,module_id='voice_A',execution_kind='CPU_REFERENCE',model_version=self.engine.lock,
                    capabilities={'streaming_asr':True,'partial':True,'hard_cancel':False},input_sample_rates=[16000],
                    tts_sample_rate=22050,max_concurrency=1,queue_bound=4,chunk_ms=200,load_ms=self.engine.load_ms);return
            if op=='cancel':
                job=self.jobs.get(r['request_id'])
                if job:job['cancelled']=True
                self.send(r,status='cancel_pending' if job else 'not_active',computation_stopped=False if job else None,was_running=bool(job and job.get('started_ns')));return
            if op=='reset':
                if sid not in self.epochs and len(self.epochs)>=8:raise ValueError('Session bound')
                self.epochs[sid]=self.epochs.get(sid,0)+1
                for j in self.jobs.values():
                    if j['sid']==sid:j['cancelled']=True
                for stream_id,s in list(self.streams.items()):
                    if s['sid']==sid:del self.streams[stream_id]
                for p in self.generated.pop(sid,[]):
                    # Only files created by this process; never input WAVs/cases.
                    safe=self.spool.path(p,sid)
                    if safe.is_file():safe.unlink()
                self.send(r,epoch=self.epochs[sid],status='reset',cancel_pending=any(j['sid']==sid for j in self.jobs.values()));return
            if op=='shutdown':
                for j in self.jobs.values():j['cancelled']=True
                self.stopping=True;self.send(r,status='shutdown_pending');return
            if op not in ('transcribe','synthesize','asr_begin','asr_push','asr_finish'):raise ValueError('Unsupported operation')
            if r['request_id'] in self.seen:raise ValueError('Duplicate request_id')
            if len(self.seen)>=4096:raise ValueError('Worker request bound; restart in maintenance window')
            if sid not in self.epochs and len(self.epochs)>=8:raise ValueError('Session bound')
            self.epochs.setdefault(sid,0)
            if 'epoch' in r and r['epoch']!=self.epochs[sid]:raise ValueError('Stale epoch')
            job={'r':r,'sid':sid,'epoch':self.epochs[sid],'cancelled':False}
            self.q.put_nowait(job);self.jobs[r['request_id']]=job;self.seen.add(r['request_id'])
    def alive(self,j):return not j['cancelled'] and j['epoch']==self.epochs[j['sid']]
    def execute(self,j):
        from .engine import wav_read
        import numpy as np
        r=j['r'];sid=j['sid'];op=r['op'];e=self.engine
        self.spool.budget()
        if op=='synthesize':
            text=r.get('text')
            if not isinstance(text,str) or not 1<=len(text)<=220 or not text.endswith(('。','！','？','!','?')):raise ValueError('Complete short text required')
            folder=self.spool.path(r.get('output_dir'),sid);folder.mkdir(parents=True,exist_ok=True)
            self.spool.budget(4*1024*1024)
            p=folder/(uuid.uuid4().hex+'.wav');result=e.synthesize(text,p)
            j['output']=p
            result.update(wav_path=p.relative_to(self.spool.root).as_posix(),text_sha256=hashlib.sha256(text.encode()).hexdigest(),wav_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),wav_ready_ns=time.monotonic_ns())
            self.spool.budget();return result
        if op=='transcribe':
            if r.get('language')!='zh':raise ValueError('Only zh supported')
            p=self.spool.path(r.get('wav_path'),sid)
            if not p.is_file():raise ValueError('Regular input file required')
            x=wav_read(p);s=e.asr.create_stream()
            return dict(text=e.decode(s,x,True),confidence=None,confidence_meaning='not_supplied_uncalibrated',final=True,
                        audio_duration_ms=len(x)/16,audio_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        if op=='asr_begin':
            if (r.get('sample_rate'),r.get('channels'),r.get('format'))!=(16000,1,'pcm_s16le'):raise ValueError('Stream format')
            if self.streams:raise ValueError('Only one active stream')
            ident=uuid.uuid4().hex
            with self.mu:
                if not self.alive(j):raise ValueError('Cancelled stream creation')
                self.streams[ident]={'sid':sid,'epoch':j['epoch'],'s':e.asr.create_stream(),'next':0,'frames':0}
                j['created_stream']=ident
            return {'stream_id':ident}
        with self.mu:
            s=self.streams.get(r.get('stream_id'))
            if not s or s['sid']!=sid or s['epoch']!=j['epoch']:raise ValueError('Foreign/stale/finished stream')
        if op=='asr_push':
            if type(r.get('seq')) is not int or r['seq']!=s['next'] or r.get('final',False) is not False:raise ValueError('Sequence/final error; use asr_finish once')
            p=self.spool.path(r.get('pcm_path'),sid)
            if not p.is_file() or p.stat().st_size!=6400:raise ValueError('Each PCM chunk must be 200ms = 6400 bytes')
            if s['frames']+3200>480000:raise ValueError('Stream 30s bound')
            x=np.frombuffer(p.read_bytes(),dtype='<i2').astype(np.float32)/32768
            text=e.decode(s['s'],x);s['next']+=1;s['frames']+=len(x)
            return {'seq':r['seq'],'ack':True,'partial_text':text,'final':False,'endpoint_detected':e.asr.is_endpoint(s['s'])}
        text=e.decode(s['s'],np.zeros(0,dtype=np.float32),True)
        with self.mu:self.streams.pop(r['stream_id'],None)
        return dict(text=text,confidence=None,final=True,audio_duration_ms=s['frames']/16)
    def run(self):
        while True:
            try:j=self.q.get(timeout=.2)
            except queue.Empty:
                if self.stopping:return
                continue
            begin=time.monotonic_ns()
            j['started_ns']=begin
            try:
                with self.mu:ok=self.alive(j)
                result=self.execute(j) if ok else None
                with self.mu:
                    if not self.alive(j):
                        if j.get('output'):j['output'].unlink(missing_ok=True)
                        self.send(j['r'],'event',status='cancelled_result_discarded',epoch=j['epoch'])
                    else:
                        if j.get('output'):self.generated.setdefault(j['sid'],[]).append(result['wav_path'])
                        self.send(j['r'],epoch=j['epoch'],compute_ms=(time.monotonic_ns()-begin)/1e6,**result)
            except Exception as exc:
                if j.get('output'):j['output'].unlink(missing_ok=True)
                self.send(j['r'],'error',code=type(exc).__name__,message=str(exc),epoch=j['epoch'])
            finally:
                with self.mu:
                    if not self.alive(j):
                        # An unacknowledged chunk may have advanced native state.
                        # Never let the caller reuse that stream after cancellation.
                        self.streams.pop(j.get('created_stream'),None)
                        self.streams.pop(j['r'].get('stream_id'),None)
                    self.jobs.pop(j['r']['request_id'],None)
                self.q.task_done()

def main():
    p=argparse.ArgumentParser();p.add_argument('--spool',required=True);p.add_argument('--endpoint-ms',type=int,default=900)
    p.add_argument('--asr-threads',type=int,default=2);p.add_argument('--tts-threads',type=int,default=2);args=p.parse_args()
    # Save a protocol-only FD, redirect even native C/C++ stdout to diagnostics.
    protocol=os.fdopen(os.dup(1),'w',encoding='utf-8',buffering=1);os.dup2(2,1)
    output_lock=threading.Lock()
    def emit(x):
        with output_lock:protocol.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');protocol.flush()
    try:
        from .engine import Engine
        worker=Worker(args.spool,emit,Engine(args.endpoint_ms,asr_threads=args.asr_threads,tts_threads=args.tts_threads))
    except Exception as exc:
        print('VOICE_STARTUP_ERROR: '+str(exc),file=sys.stderr);return 2
    while True:
        line=sys.stdin.readline(65537)
        if not line:
            worker.submit({'api_version':1,'request_id':'eof','op':'shutdown'});break
        r={}
        try:
            if len(line)>65536:
                while line and not line.endswith('\n'):line=sys.stdin.readline(65537)
                raise ValueError('Request length')
            r=json.loads(line);worker.submit(r)
        except Exception as exc:worker.send(r if isinstance(r,dict) else {},'error',code=type(exc).__name__,message=str(exc))
        if isinstance(r,dict) and r.get('op')=='shutdown':break
    worker.thread.join(timeout=60)
    if worker.thread.is_alive():return 3
    return 0
if __name__=='__main__':raise SystemExit(main())
