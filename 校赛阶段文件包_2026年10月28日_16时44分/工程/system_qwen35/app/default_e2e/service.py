"""Real A05 + A03 service, serial phases, epoch cancellation, auditable delivery."""
import hashlib,json,os,queue,re,shutil,signal,subprocess,sys,threading,time,uuid,wave
from pathlib import Path
from ..native_w4a8 import NativeW4A8
from ..audio_adapter import VoiceClient
from ..session import Session
from ..domain import digest
from .policy import ROOT,THREAD_ENV,registry,profile,new_trace,mark,clock_domain
from .resources import Sampler,mapping_memory
from .prompts import prepare
from .provenance import capture

class Cancelled(RuntimeError):pass

class TimedNative(NativeW4A8):
    def __init__(self,*args,**kwargs):self.trace=None;self.prompt_style='old';super().__init__(*args,**kwargs)
    def _record(self,x):
        super()._record(x)
        if self.trace is None:return
        ts=self.trace['timestamps'];now=time.monotonic_ns()
        if 'request' in x:ts['llm_start_ns']=now
        if x.get('type')=='token' and ts['llm_first_token_received_ns'] is None:ts['llm_first_token_received_ns']=now
    def generate(self,messages,timeout_s=20):
        messages,metadata=prepare(messages,self.prompt_style)
        if self.trace is not None:self.trace['prompt']=metadata
        self.trace_context=None if self.trace is None else {k:self.trace[k] for k in ('session_id','request_id','epoch')}
        if self.trace is not None:self.trace['native_correlation_id']=self.trace['session_id']+':'+self.trace['request_id']
        return super().generate(messages,timeout_s)

class Service:
    def __init__(self,output,*,llm_threads=3,tts_threads=2,mode='cpu_same_math',prompt_style='facts_v4',spool=None,native_manifest='modules/linear_A/manifest.a08.json'):
        self.native_manifest=native_manifest
        self.registry=registry(mode);self.profile=profile(llm_threads,tts_threads)
        if prompt_style not in ('old','short','facts_v2','facts_v3','facts_v4'):raise ValueError('Prompt style')
        self.mode=mode;self.prompt_style=prompt_style;self.output=Path(output).resolve()
        self.provenance=capture(self.profile,self.registry,prompt_style,native_manifest)
        self.output.mkdir(parents=True,exist_ok=False)
        self.spool=Path(spool).resolve() if spool else self.output/'spool'
        # Exclusive spool ownership. An existing folder is never cleaned by this service.
        self.spool.mkdir(parents=True,exist_ok=False)
        self.mu=threading.Lock();self.cancelled=threading.Event();self.phase='STARTING'
        self.epoch=0;self.count=0;self.generation=0;self.voice_generation=0;self.voice_sessions=set();self.active_voice=None;self.player=None
        self.voice=None;self.model=None;self.closed=False;self.voice_bad=False
        self.rounds=(self.output/'rounds.jsonl').open('x',encoding='utf-8')
        self.maintenance=(self.output/'maintenance.jsonl').open('x',encoding='utf-8')
        self.attempts=(self.output/'attempts.jsonl').open('x',encoding='utf-8');self.attempt_lock=threading.Lock()
        self.attempt_clock=clock_domain()
        self.start_ns=time.monotonic_ns();self.session=Session('SYN_CP_01',software_test=True);self.sid=self.session.snapshot()['session_id']
        self.sampler=Sampler(self.output/'resources.jsonl',self.pids,self.spool,lambda:self.phase)
        try:self.start_workers()
        except BaseException:self.close();raise
        self.ready_ns=time.monotonic_ns();self.phase='READY';self.save_startup()
    def pids(self):
        voice,model,player=self.voice,self.model,self.player
        return {'app':os.getpid(),'voice':voice.p.pid if voice else None,
                'model':model.p.pid if model else None,'player':player.pid if player else None}
    def journal(self,x):self.maintenance.write(json.dumps(dict(monotonic_ns=time.monotonic_ns(),**x),ensure_ascii=False)+'\n');self.maintenance.flush()
    def start_workers(self):
        self.generation+=1;self.generation_turns=0;self.voice_work_requests=0
        self.start_voice()
        self.model=TimedNative(self.output/f'model-{self.generation}',threads=self.profile['llm_threads'],kernel_threads=self.profile['kernel_threads'],
                              thread_env=THREAD_ENV,manifest_path=self.native_manifest)
        self.model.prompt_style=self.prompt_style;self.voice_bad=False
        self.journal({'event':'workers_started','generation':self.generation,'pids':self.pids(),'native_ready':self.model.ready})
    def start_voice(self):
        self.voice_generation+=1;self.voice_work_requests=0;self.voice_sessions=set()
        self.voice=VoiceClient(self.spool,self.output/f'voice-{self.voice_generation}',asr_threads=self.profile['asr_threads'],
                               tts_threads=self.profile['tts_threads'],thread_env=THREAD_ENV)
        h=self.voice.hello
        if h.get('module_id')!='voice_A' or h.get('execution_kind')!='CPU_REFERENCE' or h.get('tts_sample_rate')!=22050:raise RuntimeError('Voice identity mismatch')
        self.voice_bad=False
        self.journal({'event':'voice_started','voice_generation':self.voice_generation,'pid':self.voice.p.pid,'load_ms':h.get('load_ms')})
    def save_startup(self):
        data={'registry':self.registry,'profile':self.profile,'start_ns':self.start_ns,'ready_ns':self.ready_ns,
              'model_ready':self.model.ready,'voice_hello':self.voice.hello,'prompt_style':self.prompt_style,'provenance':self.provenance,
              'model_mapping':mapping_memory(self.model.p.pid),'network_namespace':os.readlink('/proc/self/ns/net'),
              'spool':str(self.spool),'recording':False,'medical_review':'PENDING_TEACHER_REVIEW','board':'NOT_TESTED'}
        (self.output/'startup.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    def restart(self,reason='explicit_restart'):
        if not self.mu.acquire(False):raise RuntimeError('Busy; cancel and await completion before maintenance')
        try:self._restart(reason)
        finally:self.mu.release()
    def _restart(self,reason):
        self.phase='MAINTENANCE';self.journal({'event':'restart_begin','reason':reason,'generation':self.generation})
        if self.voice:self.voice.close();self.voice=None
        if self.model:self.model.close();self.model=None
        # Session disclosure history is authoritative; native R0 replays only validated facts.
        self.session.cancel();self.epoch+=1
        self.start_workers();self.phase='READY'
        self.journal({'event':'restart_end','generation':self.generation})
    def switch_case(self,case_id):
        if not self.mu.acquire(False):raise RuntimeError('Busy; cannot switch case during turn')
        try:
            new=Session(case_id,software_test=True)
            self.journal({'event':'session_end','snapshot':self.session.snapshot(),'score':self.session.recompute_score_for_host()})
            self.session.finish();self.session=new;self.sid=new.snapshot()['session_id'];self.epoch+=1
            self.journal({'event':'case_switch','session_id':new.snapshot()['session_id'],'case_id':case_id,'epoch':self.epoch})
        finally:self.mu.release()
    def cancel(self):
        # No Session mutation races its submit lock. Owner clears/rebuilds on unwind.
        self.cancelled.set();self.epoch+=1
        if self.phase=='GENERATE' and self.model and self.model.p.poll() is None:self.model.p.send_signal(signal.SIGUSR1)
        if self.player and self.player.poll() is None:self.player.send_signal(signal.SIGUSR1)
        self.journal({'event':'cancel_requested','epoch':self.epoch,'phase':self.phase})
        return {'status':'cancel_pending','epoch':self.epoch,'acoustic_stop_verified':False}
    def check_cancel(self,epoch):
        if self.cancelled.is_set() or epoch!=self.epoch:raise Cancelled('Epoch invalidated; late result not consumable')
    def call_voice(self,op,*,timeout=60,**kw):
        self.voice_work_requests+=1
        self.voice_sessions.add(self.sid)
        handle=self.voice.begin(op,session_id=self.sid,**kw);rid=handle[0][0];self.active_voice=rid
        cancel_sent=False;deadline=time.monotonic()+timeout
        try:
            while True:
                if self.cancelled.is_set() and not cancel_sent:
                    self.voice.call('cancel',request_id=rid,timeout=2);cancel_sent=True;deadline=min(deadline,time.monotonic()+5)
                try:r=handle[1].get(timeout=min(.1,max(0,deadline-time.monotonic())))
                except queue.Empty:
                    if time.monotonic()<deadline:continue
                    # Quarantine a genuinely late/stuck worker, never reuse its native state.
                    self.voice.p.kill();self.voice.p.wait(3);self.voice_bad=True
                    raise TimeoutError('Voice deadline: owned worker stopped; explicit recovery required')
                if cancel_sent or self.cancelled.is_set():raise Cancelled('Voice cancelled/late result discarded')
                if r.get('type')!='result':raise ValueError('Voice rejected request: '+json.dumps(r,ensure_ascii=False))
                return r
        finally:
            with self.voice.mu:self.voice.pending.pop(handle[0],None)
            self.active_voice=None
    def play(self,wav,rid,epoch,trace):
        receipt=self.output/(rid+'-playback.json');err=self.output/(rid+'-playback.stderr')
        with wave.open(str(wav),'rb') as w:duration=w.getnframes()/w.getframerate()
        deadline=time.monotonic()+duration+10;cancel_at=None
        with err.open('x') as e:
            self.player=subprocess.Popen([sys.executable,'-m','system_qwen35.app.default_e2e.player',str(wav),'--receipt',str(receipt)],
                cwd=ROOT,stdout=subprocess.DEVNULL,stderr=e,env=dict(os.environ,**THREAD_ENV))
            try:
                while self.player.poll() is None:
                    if self.cancelled.is_set() or epoch!=self.epoch:
                        if cancel_at is None:self.player.send_signal(signal.SIGUSR1);cancel_at=time.monotonic()
                        if time.monotonic()-cancel_at>1:self.player.kill()
                    if time.monotonic()>deadline:self.player.kill();self.player.wait(3);raise TimeoutError('Playback deadline: owned player killed, no delivery acknowledgement')
                    time.sleep(.03)
                code=self.player.wait();r=json.loads(receipt.read_text()) if receipt.exists() else {'playback_api_completed':False,'receipt_missing':True}
                trace['playback']=dict(r,process_exit_code=code)
                for a,b in [('playback_submit_ns','playback_submit_ns'),('playback_complete_ns','playback_api_complete_ns')]:trace['timestamps'][a]=r.get(b)
                self.check_cancel(epoch)
                if code or not r.get('playback_api_completed'):raise RuntimeError('Playback failed; not delivered')
                return r
            finally:
                if self.player.poll() is None:self.player.kill();self.player.wait(3)
                self.player=None
    def transcribe(self,target,trace,stream,epoch):
        if not stream:return self.call_voice('transcribe',wav_path=self.sid+'/'+target.name,language='zh')
        if not self.voice.hello.get('capabilities',{}).get('streaming_asr'):raise RuntimeError('Streaming not supported; caller must explicitly choose WAV')
        with wave.open(str(target),'rb') as w:
            if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(16000,1,2):raise ValueError('Input format')
            h=self.call_voice('asr_begin',sample_rate=16000,channels=1,format='pcm_s16le');seq=0;partials=[]
            while True:
                raw=w.readframes(3200)
                if not raw:break
                self.check_cancel(epoch);chunk=self.spool/self.sid/'chunk.pcm';chunk.write_bytes(raw.ljust(6400,b'\0'))
                r=self.call_voice('asr_push',stream_id=h['stream_id'],seq=seq,pcm_path=self.sid+'/chunk.pcm')
                if r.get('ack') is not True or r.get('seq')!=seq:raise RuntimeError('Chunk acknowledgement mismatch')
                chunk.unlink();seq+=1;partials.append({'seq':r['seq'],'text':r.get('partial_text'),'endpoint':r.get('endpoint_detected')})
            trace['stream']={'chunk_ms':200,'ordered_acks':seq,'partials_display_only':partials,'source':'completed_synthetic_file_not_realtime_capture'}
        return self.call_voice('asr_finish',stream_id=h['stream_id'])
    def record_attempt(self,record):
        with self.attempt_lock:
            self.attempts.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n');self.attempts.flush()
    def turn(self,*,text=None,wav=None,synthetic_reference=None,stream=False,timeout_s=20,review_gate=None):
        arrival=time.monotonic_ns()
        attempt={'schema':'N02_ADMISSION_V1','request_id':uuid.uuid4().hex,'session_id':self.sid,'epoch_at_arrival':self.epoch,
                 'arrival_ns':arrival,'clock_domain':self.attempt_clock,'input_kind':'WAV' if wav is not None else 'TEXT' if text is not None else None,
                 'lock_acquired_ns':None,'maintenance_start_ns':None,'maintenance_end_ns':None,'input_submitted_ns':None,
                 'end_ns':None,'status':'ARRIVED','admission_state':'VALIDATING','lock_held':False,
                 'configuration_sha256':self.provenance['run_config_sha256'],'BOARD':'NOT_TESTED'}
        self.record_attempt(dict(attempt,event='ARRIVAL'))
        result=None
        try:
            result=self._turn(text=text,wav=wav,synthetic_reference=synthetic_reference,stream=stream,
                              timeout_s=timeout_s,review_gate=review_gate,attempt=attempt)
            attempt['status']=result['status'];attempt['answer_source']=result['answer_source'];attempt['actual_backend']=result['actual_backend']
            attempt['trace_epoch']=result['epoch'];return result
        except BaseException as exc:
            attempt['status']=('CANCELLED' if isinstance(exc,(Cancelled,KeyboardInterrupt)) else
                               'TIMEOUT' if isinstance(exc,TimeoutError) else
                               'BUSY' if attempt['admission_state']=='BUSY' else
                               'REJECTED' if attempt['admission_state']=='VALIDATING' else 'ERROR')
            attempt['error_type']=type(exc).__name__
            raise
        finally:
            # Covers a setup/namespace/filesystem error before the old round try.
            # Do not release another request's lock on the BUSY path.
            if attempt['lock_held']:
                attempt['lock_held']=False;self.mu.release()
            attempt['end_ns']=time.monotonic_ns()
            attempt['trace_present']=result is not None
            self.record_attempt(dict(attempt,event='FINISH'))
    def _turn(self,*,text=None,wav=None,synthetic_reference=None,stream=False,timeout_s=20,review_gate=None,attempt):
        if (text is None)==(wav is None):raise ValueError('Exactly one text or WAV input')
        if review_gate is not None and (wav is None or synthetic_reference is not None):raise ValueError('Human review requires ordinary WAV, not fixture confirmation')
        if not self.mu.acquire(False):
            attempt['admission_state']='BUSY';raise RuntimeError('BUSY: active turn limit 1; pending-turn queue 0')
        attempt['lock_held']=True;attempt['lock_acquired_ns']=time.monotonic_ns();attempt['admission_state']='LOCKED'
        if self.voice_work_requests>=3000 or (self.sid not in self.voice_sessions and len(self.voice_sessions)>=7):
            try:
                attempt['admission_state']='MAINTENANCE';attempt['maintenance_start_ns']=time.monotonic_ns()
                self.journal({'event':'voice_budget_maintenance','request_id':attempt['request_id'],'session_id':self.sid,
                              'requests':self.voice_work_requests,'sessions':len(self.voice_sessions)})
                self.phase='MAINTENANCE';self.voice.close();self.voice=None;self.start_voice();self.phase='READY'
            finally:attempt['maintenance_end_ns']=time.monotonic_ns()
        self.cancelled.clear();epoch=self.epoch;rid=attempt['request_id']
        tr=new_trace(self.session.snapshot()['session_id'],epoch,rid,self.mode,self.generation_turns==0)
        tr['provenance']=self.provenance
        tr['case_identity']={k:self.session.snapshot()[k] for k in ('case_id','case_version','case_sha256')}
        tr['worker_generation']=self.generation
        self.generation_turns+=1;tr['worker_generation']=self.generation;tr['voice_generation']=self.voice_generation
        self.count+=1;tr['timestamps']['input_submitted_ns']=time.monotonic_ns();self.model.trace=tr
        attempt['input_submitted_ns']=tr['timestamps']['input_submitted_ns'];attempt['admission_state']='ADMITTED'
        tr['admission']={k:attempt[k] for k in ('arrival_ns','lock_acquired_ns','maintenance_start_ns','maintenance_end_ns','configuration_sha256')}
        folder=self.spool/self.sid;folder.mkdir(exist_ok=True)
        confirmation=None;self.phase='LISTEN';mark(tr,self.phase)
        try:
            if wav is not None:
                source=Path(wav)
                if source.is_symlink() or not source.is_file() or source.stat().st_size>1024*1024:raise ValueError('Input must be regular bounded WAV <=1 MiB')
                target=folder/(rid+'.wav');shutil.copy2(source,target)
                tr['input']={'kind':'WAV','source':str(source),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'synthetic_reference':synthetic_reference}
                tr['input_file_ready_ns']=time.monotonic_ns();asr=self.transcribe(target,tr,stream,epoch)
                tr['asr']=asr;tr['timestamps']['asr_final_ns']=time.monotonic_ns()
                if asr.get('final') is not True:raise RuntimeError('Partial cannot be scored')
                text=asr['text'];norm=lambda x:''.join(re.findall('[\u4e00-\u9fff0-9]',x))
                if synthetic_reference is not None:
                    tr['asr_exact_fixture_match']=norm(text)==norm(synthetic_reference)
                    if tr['asr_exact_fixture_match']:confirmation={'kind':'SYNTHETIC_FIXTURE_EXACT_TRANSCRIPT','raw_text_digest':digest(text),'source_wav_sha256':tr['input']['sha256'],'human_review':False}
                elif review_gate is not None:
                    approved=review_gate.request(text,self.cancelled)
                    tr['asr_review']=review_gate.last
                    if approved:confirmation={'kind':'HUMAN_VERIFIED_RAW_TRANSCRIPT','raw_text_digest':digest(text),'source_wav_sha256':tr['input']['sha256'],'human_review':True}
            else:tr['input']={'kind':'TEXT','text':text}
            self.check_cancel(epoch);self.phase='GENERATE';mark(tr,self.phase)
            app=self.session.submit({'request_id':rid,'text':text,'source':'asr_final' if wav is not None else 'typed','confidence':None,'final':True},
                 self.model,timeout_s=timeout_s,trusted_asr_confirmation=confirmation)
            tr['application']=app;tr['answer_source']=app.get('answer_source')
            tr['actual_backend']='CPU_REFERENCE' if app.get('llm_calls') else None
            self.check_cancel(epoch);self.phase='VALIDATE';mark(tr,self.phase)
            if not app.get('tts_ready') or app.get('final_check',{}).get('status')!='pass':raise RuntimeError('No checked complete answer')
            tr['timestamps']['sentence_checked_ns']=app['validated_ns']
            self.phase='SYNTHESIZE';mark(tr,self.phase)
            # Both sentences are checked, then synthesized as one continuous WAV.
            # No speculative partial sentence ever reaches the vocoder.
            tts=self.call_voice('synthesize',text=app['text'],output_dir=self.sid+'/out');tr['tts']=tts
            if tts.get('text_sha256')!=hashlib.sha256(app['text'].encode()).hexdigest():raise RuntimeError('TTS text hash mismatch')
            tr['timestamps']['tts_ready_ns']=tts['wav_ready_ns'];self.check_cancel(epoch)
            self.phase='PLAY';mark(tr,self.phase)
            receipt=self.play(self.spool/tts['wav_path'],rid,epoch,tr);receipt['text_digest']=digest(app['text'])
            self.session.trusted_playback_delivery(rid,self.session.epoch,receipt)
            tr['score']=self.session.recompute_score_for_host()
            if tr['score']!=self.session.recompute_score_for_host():raise RuntimeError('Nondeterministic score')
            tr['status']='COMPLETED';tr['audio_delivery']='PULSE_DRAIN_NO_ACOUSTIC_VERIFICATION'
            tr['sentence_scheduling']={'mode':'WHOLE_CHECKED_ANSWER_SINGLE_WAV','extra_inter_request_gap_ms':None,'gap_reason':'No separate sentence submissions; internal acoustic pauses/underruns not instrumented'}
        except (Exception,KeyboardInterrupt) as e:
            if isinstance(e,KeyboardInterrupt):self.cancel()
            tr['status']='CANCELLED' if isinstance(e,(Cancelled,KeyboardInterrupt)) else 'TIMEOUT' if isinstance(e,TimeoutError) else 'ERROR'
            tr['error']={'type':type(e).__name__,'message':str(e) or 'Operator interrupted active turn','phase':self.phase}
            self.session.cancel()
        finally:
            self.model.trace=None;tr['epoch_after']=self.epoch
            if tr['timestamps']['llm_start_ns'] is not None:tr['actual_backend']='CPU_REFERENCE'
            tr['session_after']={'played_count':len(self.session.snapshot()['played']),'pending':self.session.snapshot()['pending']}
            # Reset acknowledges quiescent serial work before deleting our input/chunks.
            try:
                reset=self.voice.call('reset',session_id=self.sid,timeout=3)
                if reset.get('type')!='result' or reset.get('cancel_pending'):raise RuntimeError('Voice reset not quiescent')
                tr['voice_reset']=reset
            except Exception as e:
                self.voice_bad=True;tr['cleanup_error']=repr(e)
                if self.voice.p.poll() is None:self.voice.p.kill();self.voice.p.wait(3)
            # This exclusive directory contains only files created by this service.
            # Individual files only; never recursively delete a user-supplied directory.
            for p in folder.rglob('*'):
                if p.is_symlink():tr['cleanup_error']='Unexpected spool symlink';continue
                if p.is_file() and p.resolve().is_relative_to(self.spool):p.unlink()
            # Only remove our now-empty per-session directories, never recursively.
            for p in (folder/'out',folder):
                if p.exists() and not p.is_symlink() and p.resolve().is_relative_to(self.spool):
                    try:p.rmdir()
                    except OSError as e:tr['cleanup_error']='Owned spool directory not empty: '+str(e)
            tr['spool_after_bytes']=sum(p.stat().st_size for p in self.spool.rglob('*') if p.is_file())
            tr['voice_work_requests_since_restart']=self.voice_work_requests
            tr['voice_session_count_since_restart']=len(self.voice_sessions)
            tr['timestamps']['end_ns']=time.monotonic_ns()
            self.rounds.write(json.dumps(tr,ensure_ascii=False,allow_nan=False)+'\n');self.rounds.flush()
            self.phase='READY';attempt['lock_held']=False;self.mu.release()
        return tr
    def close(self):
        if self.closed:return
        self.closed=True
        if self.player and self.player.poll() is None:self.player.kill();self.player.wait(3)
        if self.voice:self.voice.close();self.voice=None
        if self.model:self.model.close();self.model=None
        self.sampler.close()
        (self.output/'resources-summary.json').write_text(json.dumps({'peak_simultaneous_sampled':self.sampler.peak,'sampling_interval_ms':500,
            'sampler_error':self.sampler.error,'incomplete_samples':self.sampler.incomplete_samples,
            'failed_samples':self.sampler.failed_samples,'board_memory_bytes':None,'board_budget_status':'DEPLOYMENT_PENDING_BOARD'}),encoding='utf-8')
        self.journal({'event':'service_closed'});self.rounds.close();self.maintenance.close()
        self.attempts.close()
