"""Half-duplex PC software-demo controller; models remain in persistent workers."""
import hashlib,re,shutil,signal,threading,time,uuid,wave
from pathlib import Path
from .audio_adapter import VoiceClient,HalfDuplex
from .session import Session
from .native import NativeCPU
from .domain import digest
from .pc_audio import PulseAudio
class Cancelled(Exception):pass
class VoiceLoop:
    def __init__(self,output,*,spool=None,llm_threads=3,model_backend='s0'):
        if model_backend not in ('s0','s1'):raise ValueError('Explicit s0/s1 model backend required')
        from .native_w4a8 import NativeW4A8
        self.startup_begin_ns=time.monotonic_ns()
        self.output=Path(output);self.output.mkdir(parents=True,exist_ok=False)
        self.spool=Path(spool) if spool else self.output/'spool';self.voice=VoiceClient(self.spool,self.output/'voice')
        try:self.model=(NativeW4A8 if model_backend=='s1' else NativeCPU)(self.output/'qwen',threads=llm_threads)
        except Exception:self.voice.close();raise
        try:self.player=PulseAudio();self.session=Session('SYN_CP_01',software_test=True)
        except Exception:self.voice.close();self.model.close();raise
        self.machine=HalfDuplex();self.turn_lock=threading.Lock();self.cancelled=threading.Event();self.active_voice=None
        self.sid='session';(self.spool/self.sid).mkdir()
        self.ready_ns=time.monotonic_ns()
    def cancel(self):
        self.cancelled.set();epoch=self.machine.cancel()
        if self.active_voice:self.voice.call('cancel',request_id=self.active_voice,timeout=5)
        if self.model.p.poll() is None:self.model.p.send_signal(signal.SIGUSR1)
        return {'epoch':epoch,'status':'cancel_pending','acoustic_stop_verified':False}
    def voice_call(self,op,**kw):
        rid=uuid.uuid4().hex;self.active_voice=rid
        try:
            r=self.voice.call(op,request_id=rid,session_id=self.sid,**kw)
            if r['type']!='result':raise RuntimeError(r)
            return r
        finally:self.active_voice=None
    def turn(self,wav,*,synthetic_reference=None,use_stream=True,confirm_transcript=None):
        if not self.turn_lock.acquire(False):raise RuntimeError('Half-duplex busy: one turn at a time')
        self.cancelled.clear();epoch=self.machine.epoch;rid=uuid.uuid4().hex;begin=time.monotonic_ns()
        def advance(state):
            if self.cancelled.is_set() or not self.machine.advance(state,epoch):raise Cancelled('Stale/cancelled turn')
        try:
            advance('LISTENING');target=self.spool/self.sid/(rid+'.wav');shutil.copy2(wav,target)
            if use_stream and self.voice.hello['capabilities']['streaming_asr']:
                h=self.voice_call('asr_begin',sample_rate=16000,channels=1,format='pcm_s16le')
                with wave.open(str(target),'rb') as w:
                    if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(16000,1,2):raise ValueError('Input format')
                    seq=0
                    while True:
                        raw=w.readframes(3200)
                        if not raw:break
                        if self.cancelled.is_set():raise Cancelled('Recording cancelled')
                        p=self.spool/self.sid/'chunk.pcm';p.write_bytes(raw.ljust(6400,b'\0'))
                        r=self.voice_call('asr_push',stream_id=h['stream_id'],seq=seq,pcm_path=self.sid+'/chunk.pcm')
                        if not r.get('ack'):raise RuntimeError('No input acknowledgement')
                        p.unlink();seq+=1;self.machine.display_partial(r.get('partial_text',''),epoch)
                asr=self.voice_call('asr_finish',stream_id=h['stream_id'])
            else:asr=self.voice_call('transcribe',wav_path=self.sid+'/'+target.name,language='zh')
            advance('ASR_FINAL')
            if asr.get('final') is not True:raise RuntimeError('Partial cannot enter business logic')
            confirmation=None
            if synthetic_reference is not None and confirm_transcript is not None:raise ValueError('Do not combine synthetic and human confirmation')
            if synthetic_reference is not None:
                norm=lambda x:''.join(re.findall('[\u4e00-\u9fff0-9]',x))
                if norm(synthetic_reference)==norm(asr['text']):
                    confirmation={'kind':'SYNTHETIC_FIXTURE_EXACT_TRANSCRIPT','raw_text_digest':digest(asr['text']),
                         'source_wav_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'human_review':False}
            elif confirm_transcript is not None and confirm_transcript(asr['text']) is True:
                confirmation={'kind':'HUMAN_VERIFIED_RAW_TRANSCRIPT','raw_text_digest':digest(asr['text']),
                    'source_wav_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'human_review':True}
            advance('PLANNING');advance('GENERATING')
            app=self.session.submit(dict(request_id=rid,text=asr['text'],source='asr_final',confidence=None,final=True),self.model,
                                    trusted_asr_confirmation=confirmation)
            advance('VALIDATING')
            if not app.get('tts_ready') or app.get('final_check',{}).get('status')!='pass':raise RuntimeError('No validated sentence')
            advance('SYNTHESIZING');tts=self.voice_call('synthesize',text=app['text'],output_dir=self.sid+'/out')
            if tts['text_sha256']!=hashlib.sha256(app['text'].encode()).hexdigest():raise RuntimeError('TTS text identity mismatch')
            advance('PLAYING');play=self.player.play(self.spool/tts['wav_path'],self.cancelled);play['text_digest']=digest(app['text'])
            if self.cancelled.is_set() or epoch!=self.machine.epoch or not play['playback_api_completed']:raise Cancelled('Playback cancelled')
            self.session.trusted_playback_delivery(rid,self.session.epoch,play)
            advance('READY')
            return {'domain':'PC','request_id':rid,'session_id':self.sid,'epoch':epoch,'turn_begin_ns':begin,
                 'startup_begin_ns':self.startup_begin_ns,'service_ready_ns':self.ready_ns,'voice_ready_ns':self.voice.ready_ns,
                 'first_valid_sound_ns':None,'sound_measurement':'NOT_TESTED_NO_ACOUSTIC_LOOPBACK',
                 'asr':asr,'application':app,'tts':tts,'playback':play,'trace':list(self.machine.trace),
                 'score':self.session.recompute_score_for_host(),'wave_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                 'asr_confidence':None,'human_transcript_confirmation':bool(confirmation and confirmation['human_review']),'acoustic_onset_ns':None,'board':'NOT_TESTED'}
        except Exception:
            self.machine.cancel();self.session.cancel()
            try:self.voice.call('reset',session_id=self.sid)
            except Exception:pass # primary exception remains visible; no fallback
            raise
        finally:self.turn_lock.release()
    def close(self):self.voice.close();self.model.close()
