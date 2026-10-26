"""Persistent sherpa models. No microphone/playback, case access or downloads."""
import hashlib,json,time,wave
from pathlib import Path
import numpy as np
import sherpa_onnx as so
ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'artifacts/voice_A'
ASR=ASSETS/'sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01'
TTS=ASSETS/'matcha-icefall-zh-baker'
def wav_read(path):
    with wave.open(str(path),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype())!=(1,2,16000,'NONE'):raise ValueError('Expected mono PCM16 WAV at 16000 Hz')
        n=w.getnframes()
        if not 0<n<=16000*30:raise ValueError('Audio duration must be 0..30 s')
        raw=w.readframes(n)
        if len(raw)!=n*2:raise ValueError('Truncated WAV')
    return np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768
def wav_write(path,samples,rate):
    x=np.asarray(samples)
    if x.ndim!=1 or not np.isfinite(x).all() or not len(x):raise ValueError('Invalid TTS samples')
    pcm=(np.clip(x,-1,1)*32767).round().astype('<i2')
    with path.open('xb') as f:
        with wave.open(f,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm.tobytes())
class Engine:
    def __init__(self,endpoint_ms=900,*,asr_threads=2,tts_threads=2):
        if endpoint_ms not in (600,900,1200):raise ValueError('Endpoint configuration')
        if any(type(x) is not int or not 1<=x<=4 for x in (asr_threads,tts_threads)):raise ValueError('Voice threads must be 1..4')
        self.lock=json.loads((ROOT/'modules/voice_A/resources.lock.json').read_text())
        if so.__version__!=self.lock['sherpa_onnx']:raise ValueError('sherpa version mismatch')
        required=list(ASR.glob('*.onnx'))+[ASR/'tokens.txt']+list(TTS.rglob('*'))+[ASSETS/'vocos-22khz-univ.onnx']
        for p in required:
            if p.is_dir():continue
            expected=self.lock['files'].get(p.relative_to(ROOT).as_posix())
            if p.is_symlink() or not expected or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('Missing or changed resource: '+p.name)
        begin=time.monotonic_ns()
        self.asr=so.OnlineRecognizer.from_zipformer2_ctc(tokens=str(ASR/'tokens.txt'),model=str(ASR/'model.int8.onnx'),
            num_threads=asr_threads,provider='cpu',enable_endpoint_detection=True,
            rule1_min_trailing_silence=endpoint_ms/1000,rule2_min_trailing_silence=endpoint_ms/1000,rule3_min_utterance_length=30)
        conf=so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(matcha=so.OfflineTtsMatchaModelConfig(
            acoustic_model=str(TTS/'model-steps-3.onnx'),vocoder=str(ASSETS/'vocos-22khz-univ.onnx'),
            lexicon=str(TTS/'lexicon.txt'),tokens=str(TTS/'tokens.txt')),num_threads=tts_threads,provider='cpu'),
            rule_fsts=','.join(str(TTS/n) for n in ('phone.fst','date.fst','number.fst')),max_num_sentences=2)
        if not conf.validate():raise ValueError('Invalid TTS config')
        self.tts=so.OfflineTts(conf)
        self.load_ms=(time.monotonic_ns()-begin)/1e6
    def decode(self,stream,samples,finished=False):
        stream.accept_waveform(16000,samples)
        if finished:
            # Standard recognizer flush padding, never trim source audio.
            stream.accept_waveform(16000,np.zeros(4800,dtype=np.float32));stream.input_finished()
        while self.asr.is_ready(stream):self.asr.decode_stream(stream)
        return self.asr.get_result(stream)
    def synthesize(self,text,path):
        conf=so.GenerationConfig();conf.sid=0;conf.speed=1.0;conf.silence_scale=1.0
        audio=self.tts.generate(text,conf)
        wav_write(path,audio.samples,audio.sample_rate)
        return {'frames':len(audio.samples),'sample_rate':audio.sample_rate,'speaker_id':0,'speed':1.0,'silence_scale':1.0}
