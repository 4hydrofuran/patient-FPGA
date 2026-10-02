import hashlib,json,os,queue,socket,tempfile,threading,time,unittest,wave
from pathlib import Path
from unittest.mock import patch
import numpy as np
from voicec.audio import VoiceError,inspect_wav,write_speech
from voicec.tts import Tts,validate_config,MODEL_HASH,VOCODER_HASH
from voicec.client import Client
from voicec.worker import Worker
from voicec.metrics import listening_report

ROOT=Path(__file__).resolve().parents[1]
TEST_EVIDENCE=Path(os.environ.get('VOICE_C_TEST_EVIDENCE_DIR',ROOT/'evidence/selftest_latest'))
TEST_EVIDENCE.mkdir(parents=True,exist_ok=True)


class WaveformTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c02-wave-');self.path=Path(self.tmp.name)/'out.wav'
    def tearDown(self): self.tmp.cleanup()
    def test_native_mono_pcm16_and_fixed_amplitude(self):
        result=write_speech(self.path,np.array([-1.,-.5,0.,.5,1.]),22050)
        with wave.open(str(self.path),'rb') as w:
            self.assertEqual((w.getnchannels(),w.getsampwidth(),w.getframerate()),(1,2,22050))
            self.assertEqual(np.frombuffer(w.readframes(5),dtype='<i2').tolist(),[-32768,-16384,0,16384,32767])
        self.assertEqual(result['float_out_of_range_samples'],1)
        self.assertEqual(result['audio_sha256'],hashlib.sha256(self.path.read_bytes()).hexdigest())
    def test_reject_nonfinite_stereo_empty_and_overlong(self):
        for samples in ([np.nan],[np.inf],[],[[.1,.2]],np.zeros(22050*60+1)):
            with self.assertRaises(VoiceError): write_speech(self.path,samples,22050)
            self.assertFalse(self.path.exists())
    def test_silent_output_removed(self):
        with self.assertRaises(VoiceError): write_speech(self.path,[0.,0.],22050)
        self.assertFalse(self.path.exists())
    def test_existing_output_preserved(self):
        self.path.write_bytes(b'caller-owned')
        with self.assertRaises(FileExistsError): write_speech(self.path,[.1,.2],22050)
        self.assertEqual(self.path.read_bytes(),b'caller-owned')
    def test_native_rate_not_upsampled(self):
        for rate in (8000,16000,24000,True):
            with self.assertRaises(VoiceError): write_speech(self.path,[.1,.2],rate)


class TtsConfigurationTests(unittest.TestCase):
    def setUp(self): self.config=json.loads((ROOT/'configs/tts.threads1.batch1.json').read_text())
    def test_normal_speed_pause_and_noise_fixed(self):
        for field in ('speed','length_scale','noise_scale','silence_scale'):
            for value in (.2,1.1,True,float('nan')):
                with self.assertRaises(ValueError): validate_config(self.config|{field:value})
    def test_no_untrusted_weights_or_reference_fields(self):
        for field in ('model_path','reference_text','reference_audio','lexicon','waveform_cache'):
            with self.assertRaises(ValueError): validate_config(self.config|{field:'anything'})
    def test_threads_and_batch_bounded(self):
        for thread in (True,0,3,8):
            with self.assertRaises(ValueError): validate_config(self.config|dict(num_threads=thread))
        for batch in (True,0,3):
            with self.assertRaises(ValueError): validate_config(self.config|dict(max_num_sentences=batch))
    def test_locked_weight_and_vocoder_hashes(self):
        lock=json.loads((ROOT/'assets/tts/model.lock.json').read_text(encoding='utf-8'))
        for item in lock['files']:
            self.assertEqual(hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest(),item['sha256'])
        self.assertEqual(next(i['sha256'] for i in lock['files'] if i['path'].endswith('model-steps-3.onnx')),MODEL_HASH)
        self.assertEqual(next(i['sha256'] for i in lock['files'] if i['path'].endswith('vocos-22khz-univ.onnx')),VOCODER_HASH)
    def test_real_tts_cannot_mix_with_fixtures(self):
        with self.assertRaises(ValueError): Client(ROOT/'spool',contract_tone=True,tts_config='x')


class RealTtsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('No network during TTS')):
            cls.tts=Tts(ROOT/'configs/tts.threads1.batch1.json')
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c02-tts-');self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_real_text_specific_audio_native_rate_and_unchanged_text_hash(self):
        text='我没有发热。'
        with patch.object(socket.socket,'connect',side_effect=AssertionError('No network during TTS')):
            first=self.tts.synthesize(text,self.root/'a.wav')
            second=self.tts.synthesize('练习从上午九点开始。',self.root/'b.wav')
        self.assertEqual(first['text_sha256'],hashlib.sha256(text.encode()).hexdigest())
        self.assertFalse(first['silent']);self.assertGreater(first['frames'],2205)
        self.assertEqual(first['sample_rate'],22050);self.assertEqual(first['output_kind'],'SYNTHESIZED_SPEECH')
        self.assertNotEqual(first['audio_sha256'],second['audio_sha256'])
        self.assertFalse(first['cache_hit']);self.assertIsNone(first['first_sentence_ready_ms'])
        self.assertFalse(first['internal_chunk_is_client_ready'])
    def test_cancel_before_inference_no_output(self):
        with self.assertRaises(VoiceError): self.tts.synthesize('你好。',self.root/'out.wav',lambda:True)
        self.assertFalse((self.root/'out.wav').exists())
    def test_overlong_short_answer_rejected(self):
        with self.assertRaises(VoiceError): self.tts.synthesize('字'*161,self.root/'out.wav')
        self.assertFalse((self.root/'out.wav').exists())
    def test_native_callback_one_continues_zero_stops_and_pause_explicit(self):
        import sherpa_onnx
        config=sherpa_onnx.GenerationConfig();config.sid=0;config.speed=1.;config.silence_scale=1.
        full_calls=[];stop_calls=[]
        text='你好。今天没有发热。'
        full=self.tts.engine.generate(text,config,callback=lambda s,p:full_calls.append(dict(frames=len(s),progress=p)) or 1)
        stopped=self.tts.engine.generate(text,config,callback=lambda s,p:stop_calls.append(dict(frames=len(s),progress=p)) or 0)
        self.assertGreaterEqual(len(full_calls),2);self.assertEqual(len(stop_calls),1)
        self.assertGreater(len(full.samples),len(stopped.samples))
        evidence=dict(default_generation_silence_scale=float(sherpa_onnx.GenerationConfig().silence_scale),
            actual_used_silence_scale=float(config.silence_scale),full_callbacks=full_calls,stop_callbacks=stop_calls,
            full_frames=len(full.samples),stopped_frames=len(stopped.samples),
            Python_doc_incorrect_for_Matcha='NONZERO_CONTINUES_ZERO_STOPS',quality='NOT_HUMAN_REVIEW')
        (TEST_EVIDENCE/'native_callback_check.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')


class CancellationIsolationTests(unittest.TestCase):
    def test_noninterruptible_native_fixture_cancel_discards_output_preserves_foreign_file(self):
        # Bounded native-call fixture to verify lifecycle, never speech quality evidence.
        entered=threading.Event();release=threading.Event();messages=queue.Queue()
        class NativeFixture:
            metadata={}
            def synthesize(self,text,path,cancelled):
                entered.set();release.wait(3)
                return write_speech(path,[.1]*2205,22050)
        with tempfile.TemporaryDirectory(prefix='c02-cancel-') as tmp:
            root=Path(tmp);worker=Worker(root,messages.put,tts=NativeFixture())
            try:
                worker.handle(dict(api_version=1,request_id='r1',op='synthesize',session_id='s',text='测试',output_dir='s/out'))
                self.assertTrue(entered.wait(3))
                marker=root/'s/out/foreign.txt';marker.write_text('owned-by-caller')
                worker.handle(dict(api_version=1,request_id='r2',op='cancel',target_request_id='r1'))
                worker.handle(dict(api_version=1,request_id='r3',op='reset',session_id='s'))
                release.set();worker.tasks.join()
                values=[]
                while not messages.empty():values.append(messages.get())
                self.assertFalse(any(r['request_id']=='r1' and r['type']=='result' for r in values))
                self.assertEqual(list(root.rglob('*.wav')),[]);self.assertTrue(marker.exists())
                cancel=next(r for r in values if r['request_id']=='r2')
                self.assertTrue(cancel['cancel_pending']);self.assertFalse(cancel['stopped'])
            finally:release.set();worker.close()


class RealCombinedProcessTests(unittest.TestCase):
    def test_real_tts_only_cancel_reset_and_next_session_no_late_audio(self):
        with tempfile.TemporaryDirectory(prefix='c02-real-cancel-') as tmp:
            root=Path(tmp)
            with Client(root,tts_config=ROOT/'configs/tts.threads1.batch1.json',response_timeout=60) as client:
                hello=client.call('hello');self.assertTrue(hello['capabilities']['real_tts']);self.assertFalse(hello['capabilities']['real_asr'])
                rid=client.send('synthesize',session_id='s',text='今天没有发热，也没有咳嗽。'*8,output_dir='s/out')
                self.assertEqual(client.receive(rid,terminal=False)['event'],'accepted')
                time.sleep(.03)
                cancel=client.call('cancel',target_request_id=rid)
                self.assertEqual(cancel['late_result_policy'],'DISCARD');self.assertEqual(cancel['stopped'],not cancel['cancel_pending'])
                reset=client.call('reset',session_id='s')
                done=client.call('synthesize',session_id='s',text='今天没有头痛。',output_dir='s/out')
                self.assertEqual(done['type'],'result');self.assertEqual(done['epoch'],reset['epoch'])
                with self.assertRaises(TimeoutError):client.receive(rid,timeout=.2)
                self.assertEqual(list(root.rglob('*.wav')),[root/done['wav_path']])
                (TEST_EVIDENCE/'real_tts_cancel.json').write_text(json.dumps(dict(cancel=cancel,reset=reset,next_result=done,
                    late_audio_discarded=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def test_combined_asr_tts_jsonl_old_transcript_and_cleanup(self):
        import shutil
        original=json.loads((ROOT/'data/c01_public/manifest.jsonl').read_text(encoding='utf-8').splitlines()[0])
        historical=[json.loads(s) for s in (ROOT/'evidence/c01/thread_comparison/raw.jsonl').read_text(encoding='utf-8').splitlines()]
        expected=next(r['response']['text'] for r in historical if r['recording_id']==original['recording_id'])
        with tempfile.TemporaryDirectory(prefix='c02-combined-') as tmp:
            root=Path(tmp);sid='s';(root/sid).mkdir()
            shutil.copyfile(ROOT/'data/c01_public'/original['audio_path'],root/'s/in.wav')
            with Client(root,asr_config=ROOT/'configs/asr.selected.json',tts_config=ROOT/'configs/tts.threads1.batch1.json',response_timeout=60) as client:
                hello=client.call('hello');self.assertTrue(hello['capabilities']['real_tts']);self.assertTrue(hello['capabilities']['real_asr'])
                self.assertFalse(hello['capabilities']['streaming_asr'])
                asr=client.call('transcribe',session_id=sid,language='zh',wav_path='s/in.wav')
                self.assertEqual(asr['text'],expected)
                tts=client.call('synthesize',session_id=sid,text='今天没有发热。',output_dir='s/out')
                self.assertEqual(tts['type'],'result');self.assertIsNone(tts['audible_ms'])
                self.assertEqual(inspect_wav(root/tts['wav_path'])['audio_sha256'],tts['audio_sha256'])
                marker=root/'s/out/foreign.txt';marker.write_text('caller')
                client.call('reset',session_id=sid)
                self.assertFalse((root/tts['wav_path']).exists());self.assertTrue(marker.exists());self.assertTrue((root/'s/in.wav').exists())
                (TEST_EVIDENCE/'combined_regression.json').write_text(json.dumps(dict(hello=hello,asr=asr,tts=tts,
                    original_c01_transcript=expected,original_audio_sha256=original['audio_sha256'],
                    old_transcript_preserved=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


class ListeningPacketTests(unittest.TestCase):
    def test_missing_human_review_cannot_become_score(self):
        forms=[json.loads(s) for s in (ROOT/'listening/c02/blank_forms.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(forms),14)
        report=listening_report(forms);self.assertEqual(report['reviewed'],0);self.assertEqual(report['pending'],14)
        self.assertIsNone(report['intelligibility']);self.assertIsNone(report['naturalness'])
        for row in forms:
            self.assertEqual(row['audio_sha256'],hashlib.sha256((ROOT/row['audio_path']).read_bytes()).hexdigest())
            for field in ('heard_transcript','negation_error','number_error','omission','intelligibility_score','naturalness_score'):
                self.assertIsNone(row[field])


if __name__=='__main__':unittest.main()
