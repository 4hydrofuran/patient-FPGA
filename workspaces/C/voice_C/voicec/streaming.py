"""Bounded raw PCM16 chunks; native CTC endpoint advice, explicit single final."""
import hashlib,json,time
from pathlib import Path
from .audio import VoiceError

STREAM_OPS=['asr_begin','asr_push','asr_finish']


def validate_config(c):
    fixed=dict(api_version=1,chunk_ms=200,max_audio_seconds=60,max_chunks=1024,
        max_streams_per_process=64,idle_timeout_seconds=15,endpoint_policy='ADVISORY_UNTIL_EXPLICIT_FINISH',
        tail_padding_ms=660,rule1_min_trailing_silence=2.4,rule3_min_utterance_length=20.0)
    if not isinstance(c,dict) or set(c)!=set(fixed)|{'rule2_min_trailing_silence'}:
        raise ValueError('Streaming configuration fields differ from fixed policy')
    for k,v in fixed.items():
        if type(v) is int and type(c[k]) is not int:raise ValueError('Integer configuration required')
        if isinstance(c[k],bool) or c[k]!=v:raise ValueError('Unexpected streaming configuration: '+k)
    if type(c['rule2_min_trailing_silence']) not in (int,float) or c['rule2_min_trailing_silence'] not in (.8,1.2,1.6):
        raise ValueError('Development endpoint candidates are 0.8, 1.2 or 1.6 seconds')
    return dict(c)


def read_chunk(path):
    with Path(path).open('rb') as f:raw=f.read(6401)
    if not raw or len(raw)>6400 or len(raw)%2:
        raise VoiceError('BAD_PCM_CHUNK','Require 1..3200 little-endian PCM16 samples, at most 200 ms')
    if raw[:4] in (b'RIFF',b'RIFX'):
        raise VoiceError('BAD_PCM_CHUNK','asr_push requires raw PCM bytes, not a WAV container')
    return raw


class StreamingAsr:
    def __init__(self,asr,config):
        self.asr=asr;self.config=validate_config(config)
        self.metadata=asr.metadata|dict(public_streaming_ops=True,streaming_config=self.config,
            endpoint_policy='ADVISORY_ONLY_NO_AUDIO_DISCARD',partial_policy='DISPLAY_ONLY',
            commit_policy='ASR_FINISH_RESULT_ONLY',chunk_encoding='RAW_PCM_S16LE')

    def begin(self,state):
        state['native']=self.asr.recognizer.create_stream()
        state.update(frames=0,steps=0,compute_ms=0.,pcm_hash=hashlib.sha256(),
            silent=True,clipped_samples=0,last_partial='',endpoint=False,endpoint_first_audio_ms=None)

    def decode(self,state,cancelled):
        count=0
        while self.asr.recognizer.is_ready(state['native']):
            if cancelled():raise VoiceError('CANCELLED','Stream cancelled between native decoder steps')
            self.asr.recognizer.decode_stream(state['native']);count+=1
        state['steps']+=count

    def push(self,state,path,cancelled):
        start=time.perf_counter();raw=read_chunk(path)
        frames=len(raw)//2
        if state['frames']+frames>16000*self.config['max_audio_seconds']:
            raise VoiceError('STREAM_AUDIO_LIMIT','Stream exceeds 60 seconds; no audio trimmed')
        if cancelled():raise VoiceError('CANCELLED','Stream cancelled before chunk consumption')
        pcm=self.asr.np.frombuffer(raw,dtype='<i2')
        samples=pcm.astype(self.asr.np.float32)/32768.
        state['native'].accept_waveform(16000,samples)
        self.decode(state,cancelled)
        state['frames']+=frames;state['pcm_hash'].update(raw)
        state['silent']&=bool(self.asr.np.all(pcm==0))
        state['clipped_samples']+=int(self.asr.np.count_nonzero((pcm==-32768)|(pcm==32767)))
        text=self.asr.recognizer.get_result(state['native'])
        endpoint=self.asr.recognizer.is_endpoint(state['native'])
        changed=text!=state['last_partial'];state['last_partial']=text
        if endpoint and state['endpoint_first_audio_ms'] is None:state['endpoint_first_audio_ms']=state['frames']/16
        state['endpoint']=endpoint
        state['compute_ms']+=(time.perf_counter()-start)*1000
        return dict(ack=True,consumed=True,chunk_frames=frames,chunk_sha256=hashlib.sha256(raw).hexdigest(),
            audio_duration_ms=state['frames']/16,endpoint_detected=endpoint,endpoint_is_advisory=True),text,changed

    def finish(self,state,cancelled):
        if not state['frames']:raise VoiceError('EMPTY_STREAM','Cannot finalize a stream without PCM')
        start=time.perf_counter()
        state['native'].accept_waveform(16000,self.asr.np.zeros(10560,dtype=self.asr.np.float32))
        state['native'].input_finished();self.decode(state,cancelled)
        state['compute_ms']+=(time.perf_counter()-start)*1000
        text=self.asr.recognizer.get_result(state['native'])
        return dict(text=text,final=True,commit_allowed=True,confidence=None,sample_rate=16000,
            frames=state['frames'],audio_duration_ms=state['frames']/16,pcm_sha256=state['pcm_hash'].hexdigest(),
            decode_steps=state['steps'],silent=state['silent'],clipped_samples=state['clipped_samples'],
            stream_compute_ms=state['compute_ms'],tail_padding_ms=660,
            endpoint_first_audio_ms=state['endpoint_first_audio_ms'],endpoint_policy=self.config['endpoint_policy'],
            amplitude_policy='PCM16_DIV_32768_NO_AGC_NO_TRIM_NO_VAD_DISCARD')
