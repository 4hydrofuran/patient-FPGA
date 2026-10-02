import hashlib,json,os,queue,socket,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from voicec.asr import Asr
from voicec.audio import VoiceError,read_pcm16
from voicec.client import Client
from voicec.streaming import StreamingAsr,read_chunk,validate_config
from voicec.worker import Worker

ROOT=Path(__file__).resolve().parents[1]


class StreamingInputTests(unittest.TestCase):
    def test_endpoint_configs_and_bounded_policy(self):
        c=json.loads((ROOT/'configs/stream.selected.json').read_text())
        for threshold in (.8,1.2,1.6):self.assertEqual(validate_config(c|dict(rule2_min_trailing_silence=threshold))['chunk_ms'],200)
        for edit in (dict(chunk_ms=400),dict(max_audio_seconds=120),dict(endpoint_policy='AUTO_TRUNCATE'),dict(rule2_min_trailing_silence=True),dict(api_version=True),dict(reference_text='答案')):
            with self.assertRaises(ValueError):validate_config(c|edit)
    def test_raw_pcm_bounds_and_wav_rejected(self):
        with tempfile.TemporaryDirectory(prefix='c03-pcm-') as tmp:
            p=Path(tmp)/'chunk.pcm'
            for raw in (b'',b'x',b'\0'*6402,b'RIFF'+b'\0'*100):
                p.write_bytes(raw)
                with self.assertRaises(VoiceError):read_chunk(p)
            p.write_bytes(b'\0\0'*3200);self.assertEqual(len(read_chunk(p)),6400)
    def test_streaming_requires_asr(self):
        with self.assertRaises(ValueError):Client(ROOT/'spool',stream_config='x')


class RealStreamStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg=json.loads((ROOT/'configs/stream.selected.json').read_text())
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')):
            cls.asr=Asr(ROOT/'configs/asr.selected.json',endpoint_config=cfg)
        cls.engine=StreamingAsr(cls.asr,cfg)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c03-state-');self.root=Path(self.tmp.name);(self.root/'s').mkdir()
        (self.root/'s/chunk.pcm').write_bytes(b'\0\0'*3200)
        self.messages=queue.Queue();self.worker=Worker(self.root,self.messages.put,asr=self.asr,streaming=self.engine)
        self.seq=0;self.pending=[]
    def tearDown(self):self.worker.close();self.tmp.cleanup()
    def call(self,op,**fields):
        self.seq+=1;rid=f'test-{self.seq}';self.worker.handle(dict(api_version=1,request_id=rid,op=op,**fields))
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            for i,row in enumerate(self.pending):
                if row['request_id']==rid and row['type']!='event':return self.pending.pop(i)
            self.pending.append(self.messages.get(timeout=10))
        self.fail('No terminal response')
    def begin(self):
        row=self.call('asr_begin',session_id='s',sample_rate=16000,channels=1,format='pcm_s16le')
        self.assertEqual(row['type'],'result');return row['stream_id']
    def push(self,stream,seq=0,**extra):return self.call('asr_push',stream_id=stream,seq=seq,pcm_path='s/chunk.pcm',**extra)
    def test_hello_opt_in_and_format_validation(self):
        hello=self.call('hello');self.assertTrue(hello['capabilities']['streaming_asr'])
        for edit in (dict(sample_rate=8000),dict(channels=2),dict(format='wav'),dict(sample_rate=True)):
            r=dict(session_id='s',sample_rate=16000,channels=1,format='pcm_s16le')|edit
            self.assertEqual(self.call('asr_begin',**r)['code'],'BAD_STREAM_FORMAT')
    def test_seq_zero_monotonic_duplicate_and_bool_rejected(self):
        stream=self.begin()
        for seq in (-1,1,True):self.assertEqual(self.push(stream,seq)['code'],'BAD_SEQ')
        self.assertTrue(self.push(stream,0)['ack'])
        self.assertEqual(self.push(stream,0)['code'],'BAD_SEQ')
        self.assertTrue(self.push(stream,1)['ack'])
    def test_final_input_then_unique_final_result(self):
        stream=self.begin();ack=self.push(stream,final=True);self.assertTrue(ack['input_closed'])
        self.assertEqual(self.push(stream,1)['code'],'STREAM_INPUT_CLOSED')
        result=self.call('asr_finish',stream_id=stream)
        self.assertTrue(result['final']);self.assertTrue(result['commit_allowed']);self.assertEqual(result['frames'],3200)
        self.assertEqual(result['pcm_sha256'],hashlib.sha256(b'\0\0'*3200).hexdigest())
        self.assertEqual(self.call('asr_finish',stream_id=stream)['code'],'STREAM_CLOSED')
    def test_empty_finish_error_frees_half_duplex(self):
        stream=self.begin();self.assertEqual(self.call('asr_finish',stream_id=stream)['code'],'EMPTY_STREAM')
        self.assertIsNone(self.worker.active_stream);self.begin()
    def test_half_duplex_no_tts_or_file_asr_during_stream(self):
        stream=self.begin()
        self.assertEqual(self.call('synthesize',session_id='s',text='测试',output_dir='s/out')['code'],'HALF_DUPLEX_BUSY')
        self.assertEqual(self.call('asr_begin',session_id='other',sample_rate=16000,channels=1,format='pcm_s16le')['code'],'HALF_DUPLEX_BUSY')
        self.push(stream);self.call('asr_finish',stream_id=stream)
        self.assertEqual(self.call('synthesize',session_id='s',text='测试',output_dir='s/out')['code'],'MODEL_NOT_CONFIGURED')
    def test_reset_epoch_rejects_old_stream_preserves_chunk(self):
        stream=self.begin();self.push(stream)
        reset=self.call('reset',session_id='s');self.assertEqual(reset['epoch'],1)
        self.assertEqual(self.push(stream,1)['code'],'STALE_STREAM');self.assertTrue((self.root/'s/chunk.pcm').exists())
        self.assertNotEqual(self.begin(),stream)
    def test_missing_and_cross_session_chunk_do_not_advance_seq(self):
        stream=self.begin()
        for path,code in [('s/missing.pcm','FILE_NOT_FOUND'),('other/chunk.pcm','CROSS_SESSION_PATH'),('../x','UNSAFE_PATH'),('https://example.com/x','UNSAFE_PATH')]:
            r=self.call('asr_push',stream_id=stream,seq=0,pcm_path=path)
            self.assertEqual(r['code'],code)
        self.assertTrue(self.push(stream,0)['ack'])
    def test_corrupt_chunk_abort_prevents_incomplete_final(self):
        stream=self.begin();(self.root/'s/chunk.pcm').write_bytes(b'x')
        self.assertEqual(self.push(stream)['code'],'BAD_PCM_CHUNK');self.assertIsNone(self.worker.active_stream)
        self.assertEqual(self.call('asr_finish',stream_id=stream)['code'],'STREAM_CLOSED')
    def test_chunk_and_duration_resource_limits(self):
        stream=self.begin();state=self.worker.streams[stream]
        state['next_seq']=1024
        self.assertEqual(self.push(stream,1024)['code'],'STREAM_CHUNK_LIMIT')
        state['next_seq']=0;state['frames']=16000*60
        self.assertEqual(self.push(stream)['code'],'STREAM_AUDIO_LIMIT');self.assertIsNone(self.worker.active_stream)
    def test_process_stream_limit_is_bounded(self):
        for _ in range(64):self.call('asr_finish',stream_id=self.begin())
        self.assertEqual(self.call('asr_begin',session_id='s',sample_rate=16000,channels=1,format='pcm_s16le')['code'],'STREAM_LIMIT')
    def test_idle_lease_expiration_releases_resident_stream(self):
        stream=self.begin();self.worker.streams[stream]['last_activity']-=16
        self.worker.expire_streams()
        self.assertIsNone(self.worker.active_stream);self.assertIsNone(self.worker.streams[stream]['native'])
        self.assertEqual(self.push(stream)['code'],'STREAM_CLOSED');self.begin()
    def test_unknown_id_and_bad_final_rejected(self):
        self.assertEqual(self.push('not-found')['code'],'UNKNOWN_STREAM')
        stream=self.begin();self.assertEqual(self.push(stream,final=1)['code'],'BAD_FINAL')
        self.assertTrue(self.push(stream,final=False)['ack'])
    def test_queued_cancel_discards_running_stream_and_late_partial(self):
        stream=self.begin();entered=threading.Event();release=threading.Event();original=self.engine.push
        def delayed(*args):entered.set();release.wait(5);return original(*args)
        with patch.object(self.engine,'push',side_effect=delayed):
            self.worker.handle(dict(api_version=1,request_id='running',op='asr_push',stream_id=stream,seq=0,pcm_path='s/chunk.pcm'))
            self.assertTrue(entered.wait(5))
            self.worker.handle(dict(api_version=1,request_id='queued',op='asr_push',stream_id=stream,seq=1,pcm_path='s/chunk.pcm'))
            cancel=self.call('cancel',target_request_id='queued');self.assertTrue(cancel['cancel_pending']);self.assertFalse(cancel['stopped'])
            release.set();self.worker.tasks.join()
        rows=self.pending[:]
        while not self.messages.empty():rows.append(self.messages.get())
        self.assertFalse(any(r['request_id'] in ('running','queued') and (r['type']=='result' or r.get('event')=='partial') for r in rows))
        self.assertIsNone(self.worker.active_stream);self.assertTrue((self.root/'s/chunk.pcm').exists())
    def test_reset_pending_decode_old_epoch_not_emitted(self):
        stream=self.begin();entered=threading.Event();release=threading.Event();original=self.engine.push
        def delayed(*args):entered.set();release.wait(5);return original(*args)
        with patch.object(self.engine,'push',side_effect=delayed):
            self.worker.handle(dict(api_version=1,request_id='old',op='asr_push',stream_id=stream,seq=0,pcm_path='s/chunk.pcm'))
            self.assertTrue(entered.wait(5));self.call('reset',session_id='s');release.set();self.worker.tasks.join()
        rows=self.pending[:]
        while not self.messages.empty():rows.append(self.messages.get())
        self.assertFalse(any(r['request_id']=='old' and r['type']!='event' for r in rows))
        self.assertEqual(self.push(stream,1)['code'],'STALE_STREAM');self.begin()

    def test_pipeline_corrupt_chunk_returns_errors_for_accepted_followup(self):
        stream=self.begin();entered=threading.Event();release=threading.Event();original=self.engine.push
        (self.root/'s/bad.pcm').write_bytes(b'x')
        def delayed(*args):entered.set();release.wait(5);return original(*args)
        with patch.object(self.engine,'push',side_effect=delayed):
            self.worker.handle(dict(api_version=1,request_id='bad',op='asr_push',stream_id=stream,seq=0,pcm_path='s/bad.pcm'))
            self.assertTrue(entered.wait(5))
            self.worker.handle(dict(api_version=1,request_id='after-bad',op='asr_push',stream_id=stream,seq=1,pcm_path='s/chunk.pcm'))
            release.set();self.worker.tasks.join()
        rows=[]
        while not self.messages.empty():rows.append(self.messages.get())
        self.assertEqual(next(r['code'] for r in rows if r['request_id']=='bad' and r['type']=='error'),'BAD_PCM_CHUNK')
        self.assertEqual(next(r['code'] for r in rows if r['request_id']=='after-bad' and r['type']=='error'),'STREAM_ABORTED')

    def test_request_budget_rejects_without_creating_stream(self):
        self.worker.requests.update(f'used-{i}' for i in range(4096))
        result=self.call('asr_begin',session_id='s',sample_rate=16000,channels=1,format='pcm_s16le')
        self.assertEqual(result['code'],'REQUEST_LIMIT');self.assertIsNone(self.worker.active_stream)

    def test_duplicate_request_id_does_not_consume_pcm_twice(self):
        stream=self.begin();r=dict(api_version=1,request_id='duplicate',op='asr_push',stream_id=stream,seq=0,pcm_path='s/chunk.pcm')
        self.worker.handle(r);self.worker.tasks.join()
        self.worker.handle(r|dict(seq=1))
        rows=[]
        while not self.messages.empty():rows.append(self.messages.get())
        self.assertEqual(next(r['code'] for r in rows if r['type']=='error'),'DUPLICATE_ID')
        final=self.call('asr_finish',stream_id=stream);self.assertEqual(final['frames'],3200)

    def test_stream_queue_bound_rejection_does_not_advance_seq(self):
        stream=self.begin();entered=threading.Event();release=threading.Event();original=self.engine.push
        def delayed(*args):entered.set();release.wait(5);return original(*args)
        with patch.object(self.engine,'push',side_effect=delayed):
            for seq in range(3):
                self.worker.handle(dict(api_version=1,request_id=f'queued-{seq}',op='asr_push',stream_id=stream,seq=seq,pcm_path='s/chunk.pcm'))
                if seq==0:self.assertTrue(entered.wait(5))
            busy=self.push(stream,3);self.assertEqual(busy['code'],'BUSY')
            self.assertEqual(self.worker.streams[stream]['next_seq'],3)
            release.set();self.worker.tasks.join()
        self.assertTrue(self.push(stream,3)['ack'])
        self.assertEqual(self.call('asr_finish',stream_id=stream)['frames'],12800)


class RealStreamingProcessTests(unittest.TestCase):
    def test_full_public_audio_partial_display_final_once_ack_then_delete(self):
        row=json.loads((ROOT/'data/c01_public/manifest.jsonl').read_text(encoding='utf-8').splitlines()[0])
        info,pcm=read_pcm16(ROOT/'data/c01_public'/row['audio_path'],asr=True)
        old=[json.loads(s) for s in (ROOT/'evidence/c01/thread_comparison/raw.jsonl').read_text(encoding='utf-8').splitlines()]
        expected=next(r['response']['text'] for r in old if r['recording_id']==row['recording_id'])
        trace=[]
        with tempfile.TemporaryDirectory(prefix='c03-process-') as tmp:
            root=Path(tmp);(root/'s').mkdir()
            with Client(root,asr_config=ROOT/'configs/asr.selected.json',stream_config=ROOT/'configs/stream.selected.json',response_timeout=60,trace_callback=trace.append) as c:
                hello=c.call('hello');self.assertTrue(hello['capabilities']['streaming_asr'])
                stream=c.call('asr_begin',session_id='s',sample_rate=16000,channels=1,format='pcm_s16le')['stream_id']
                for seq,offset in enumerate(range(0,len(pcm),6400)):
                    p=root/'s/chunk.pcm';p.write_bytes(pcm[offset:offset+6400])
                    ack=c.call('asr_push',stream_id=stream,seq=seq,pcm_path='s/chunk.pcm')
                    self.assertTrue(ack['consumed']);p.unlink();c.drain_events()
                result=c.call('asr_finish',stream_id=stream)
                self.assertEqual(result['text'],expected);self.assertEqual(result['frames'],info['frames'])
                self.assertEqual(result['pcm_sha256'],hashlib.sha256(pcm).hexdigest())
                self.assertEqual(c.call('asr_finish',stream_id=stream)['code'],'STREAM_CLOSED')
        partials=[r['message'] for r in trace if r['direction']=='response' and r['message'].get('event')=='partial']
        self.assertTrue(partials)
        self.assertTrue(all(r['display_only'] and not r['commit_allowed'] and not r['final'] for r in partials))
        finals=[r['message'] for r in trace if r['direction']=='response' and r['message'].get('final') is True]
        self.assertEqual(len(finals),1)


if __name__=='__main__':unittest.main()
