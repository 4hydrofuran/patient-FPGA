"""App-controlled PulseAudio Unix playback. Acoustic onset is deliberately null."""
import ctypes as C
import math,struct,threading,time,wave

class CaptureBuffer:
    """Bounded unmodified PCM; readiness means a first block was received."""
    CHUNK_BYTES=6400
    def __init__(self,max_seconds=15):
        if type(max_seconds) not in (int,float) or not math.isfinite(max_seconds) or not .2<=max_seconds<=15:raise ValueError('Recording limit must be 0.2..15 seconds')
        self.max_chunks=int(max_seconds*5);self.chunks=[]
        self.first_chunk_ns=None;self.ready_announced_ns=None
    @property
    def full(self):return len(self.chunks)>=self.max_chunks
    def append(self,raw,received_ns):
        if self.full:raise ValueError('Capture duration limit')
        if not isinstance(raw,bytes) or len(raw)!=self.CHUNK_BYTES:raise ValueError('Capture block must be 200ms PCM16 mono')
        self.chunks.append(raw)
        if self.first_chunk_ns is None:self.first_chunk_ns=received_ns
    def announce_ready(self,callback=None):
        if not self.chunks:raise RuntimeError('Cannot announce readiness before receiving audio')
        if self.ready_announced_ns is not None:raise RuntimeError('Readiness already announced')
        self.ready_announced_ns=time.monotonic_ns()
        if callback:callback()
    def pcm(self):return b''.join(self.chunks)
    def diagnostics(self):
        if not self.chunks:raise ValueError('No captured audio')
        values=[x[0] for x in struct.iter_unpack('<h',self.pcm())]
        rms=lambda xs:math.sqrt(sum(x*x for x in xs)/len(xs))/32768
        return {'frames':len(values),'duration_ms':len(values)/16,'peak_fraction':max(abs(x) for x in values)/32768,
            'rms_fraction':rms(values),'dc_fraction':sum(values)/len(values)/32768,
            'clipped_sample_count':sum(x in (-32768,32767) for x in values),
            'zero_sample_fraction':sum(x==0 for x in values)/len(values),
            'first_200ms_rms_fraction':rms(values[:3200]),'last_200ms_rms_fraction':rms(values[-3200:]),
            'first_chunk_received_ns':self.first_chunk_ns,'ready_announced_ns':self.ready_announced_ns,
            'meaning':'Unmodified PCM signal statistics, not VAD, ASR confidence or acoustic word alignment'}
class SampleSpec(C.Structure):_fields_=[('format',C.c_int),('rate',C.c_uint32),('channels',C.c_uint8)]
class BufferAttr(C.Structure):_fields_=[('maxlength',C.c_uint32),('tlength',C.c_uint32),('prebuf',C.c_uint32),('minreq',C.c_uint32),('fragsize',C.c_uint32)]
class PulseAudio:
    def __init__(self):
        self.lib=C.CDLL('libpulse-simple.so.0')
        self.lib.pa_simple_new.restype=C.c_void_p
        self.lib.pa_simple_new.argtypes=[C.c_char_p,C.c_char_p,C.c_int,C.c_char_p,C.c_char_p,C.POINTER(SampleSpec),C.c_void_p,C.POINTER(BufferAttr),C.POINTER(C.c_int)]
        for name in ('pa_simple_write','pa_simple_read'):
            f=getattr(self.lib,name);f.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_int)];f.restype=C.c_int
        for name in ('pa_simple_drain','pa_simple_flush'):
            f=getattr(self.lib,name);f.argtypes=[C.c_void_p,C.POINTER(C.c_int)];f.restype=C.c_int
        self.lib.pa_simple_free.argtypes=[C.c_void_p]
    def record_push_to_talk(self,path,stop,*,recording_authorized=False,max_seconds=15,on_ready=None,stop_requested=None):
        if recording_authorized is not True:raise PermissionError('Explicit microphone consent required')
        capture=CaptureBuffer(max_seconds);open_begin=time.monotonic_ns()
        error=C.c_int();spec=SampleSpec(3,16000,1)
        conn=self.lib.pa_simple_new(b'unix:/mnt/wslg/PulseServer',b'patient-FPGA-A03',2,None,b'authorized-synthetic-recording',C.byref(spec),None,None,C.byref(error))
        if not conn:raise RuntimeError('Microphone open failed: '+str(error.value))
        start=time.monotonic_ns()
        try:
            while not stop.is_set() and not capture.full:
                if stop_requested is not None and stop_requested():stop.set();break
                buf=C.create_string_buffer(6400)
                if self.lib.pa_simple_read(conn,buf,6400,C.byref(error))<0:raise RuntimeError('Microphone read failed')
                capture.append(buf.raw,time.monotonic_ns())
                # First block is retained, never thrown away as warm-up audio.
                if capture.ready_announced_ns is None:capture.announce_ready(on_ready)
        finally:self.lib.pa_simple_free(conn)
        end=time.monotonic_ns();diagnostics=capture.diagnostics()
        with path.open('xb') as f:
            with wave.open(f,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(capture.pcm())
        return {'sampling_rate':16000,'channels':1,'frames':len(capture.chunks)*3200,
            'device_open_requested_ns':open_begin,'record_begin_ns':start,'record_end_ns':end,
            'stop_reason':'duration_limit' if capture.full else 'user_stop','diagnostics':diagnostics,
            'origin':'USER_AUTHORIZED_SYNTHETIC_READING','raw_audio_retention':'temporary'}
    def play(self,path,cancel=None):
        cancel=cancel or threading.Event();error=C.c_int()
        with wave.open(str(path),'rb') as w:
            if w.getnchannels()!=1 or w.getsampwidth()!=2:raise ValueError('PCM16 mono playback required')
            rate=w.getframerate();spec=SampleSpec(3,rate,1) # PA_SAMPLE_S16LE
            attr=BufferAttr(0xffffffff,int(rate*.2)*2,0xffffffff,0xffffffff,0xffffffff)
            conn=self.lib.pa_simple_new(b'unix:/mnt/wslg/PulseServer',b'patient-FPGA-A03',1,None,b'synthetic-test',C.byref(spec),None,C.byref(attr),C.byref(error))
            if not conn:raise RuntimeError('Pulse playback open failed: '+str(error.value))
            submit=time.monotonic_ns();frames=0
            try:
                while not cancel.is_set():
                    chunk=w.readframes(int(rate*.2))
                    if not chunk:break
                    if self.lib.pa_simple_write(conn,chunk,len(chunk),C.byref(error))<0:raise RuntimeError('Pulse write failed')
                    frames+=len(chunk)//2
                if cancel.is_set():self.lib.pa_simple_flush(conn,C.byref(error))
                elif self.lib.pa_simple_drain(conn,C.byref(error))<0:raise RuntimeError('Pulse drain failed')
                completed=time.monotonic_ns()
            finally:self.lib.pa_simple_free(conn)
        return dict(playback_submit_ns=submit,playback_api_complete_ns=completed,acoustic_onset_ns=None,
                    playback_api_completed=not cancel.is_set(),cancelled=cancel.is_set(),frames_submitted=frames,
                    sample_rate=rate,device='WSLg PulseAudio default sink via Unix socket',
                    timing_kind='SOFTWARE_SUBMISSION_AND_DRAIN_NOT_ACOUSTIC_MEASUREMENT')
