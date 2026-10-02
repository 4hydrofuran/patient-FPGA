import hashlib
import json
import socket
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from voicec.asr import Asr,validate_config,MODEL_HASH,TOKEN_HASH
from voicec.audio import VoiceError,read_pcm16
from voicec.client import Client
from voicec.prepare_audio import resample_24k_to_16k

ROOT=Path(__file__).resolve().parents[1]


def wav(path,pcm,rate=16000):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as f:
        f.setparams((1,2,rate,0,'NONE','not compressed')); f.writeframes(pcm)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'configs/asr.threads1.json').read_text())

    def test_thread_choices_and_fixed_padding(self):
        for threads in [1,2,4]:
            self.assertEqual(validate_config(self.config|{'num_threads':threads})['num_threads'],threads)

    def test_invalid_threads_and_bool_rejected(self):
        for threads in [True,0,3,8]:
            with self.assertRaises(ValueError): validate_config(self.config|{'num_threads':threads})

    def test_answer_hotword_or_path_fields_rejected(self):
        for field in ['hotwords','reference_text','model_path','tokens','rule_fsts']:
            with self.assertRaises(ValueError): validate_config(self.config|{field:'anything'})

    def test_non_cpu_or_beam_search_rejected(self):
        for edit in [dict(provider='cuda'),dict(decoding_method='modified_beam_search'),dict(tail_padding_ms=0)]:
            with self.assertRaises(ValueError): validate_config(self.config|edit)

    def test_real_and_contract_flags_cannot_mix(self):
        with self.assertRaises(ValueError): Client(ROOT/'data/c01_public',contract_tone=True,asr_config='x')

    def test_locked_asset_hashes(self):
        d=ROOT/'assets/asr/zipformer-small-ctc-zh-int8-2025-04-01'
        self.assertEqual(hashlib.sha256((d/'model.int8.onnx').read_bytes()).hexdigest(),MODEL_HASH)
        self.assertEqual(hashlib.sha256((d/'tokens.txt').read_bytes()).hexdigest(),TOKEN_HASH)

    def test_resample_keeps_duration_dc_and_rejects_out_of_band(self):
        import numpy as np
        t=np.arange(24000)/24000
        def converted(signal):
            return np.frombuffer(resample_24k_to_16k(np.rint(signal).astype('<i2').tobytes()),dtype='<i2').astype(float)
        dc=converted(np.full(24000,1000))
        self.assertEqual(len(dc),16000);self.assertTrue(np.all(dc==1000))
        low=converted(10000*np.sin(2*np.pi*1000*t))
        high=converted(10000*np.sin(2*np.pi*10000*t))
        self.assertGreater(np.sqrt(np.mean(low[100:-100]**2)),6500)
        self.assertLess(np.sqrt(np.mean(high[100:-100]**2)),50)


class RealAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Python-level connection guard. Does not claim a physically disconnected machine.
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden during ASR')):
            cls.asr=Asr(ROOT/'configs/asr.threads1.json')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='voice-c01-');self.root=Path(self.tmp.name)

    def tearDown(self): self.tmp.cleanup()

    def test_silence_real_decoder_and_repeat_isolation(self):
        path=self.root/'s/in.wav';wav(path,b'\0\0'*16000)
        first=self.asr.transcribe(path);second=self.asr.transcribe(path)
        self.assertEqual(first['text'],second['text']);self.assertTrue(first['silent'])
        self.assertIn('SILENT_INPUT',first['warnings']);self.assertIsNone(first['confidence'])
        self.assertGreater(first['decode_steps'],0)

    def test_short_clipped_audio_is_recorded_not_trimmed(self):
        path=self.root/'s/in.wav';wav(path,b'\xff\x7f'*320)
        result=self.asr.transcribe(path)
        self.assertEqual(result['frames'],320);self.assertEqual(result['clipped_samples'],320)
        self.assertIn('VERY_SHORT_INPUT',result['warnings']);self.assertIn('CLIPPED_INPUT',result['warnings'])

    def test_pcm_snapshot_matches_hash_and_amplitude_endpoints(self):
        path=self.root/'s/in.wav';wav(path,b'\x00\x80\xff\x7f\0\0')
        info,pcm=read_pcm16(path,asr=True)
        samples=self.asr.np.frombuffer(pcm,dtype='<i2').astype(self.asr.np.float32)/32768.0
        self.assertEqual(float(samples[0]),-1.0);self.assertLess(float(samples[1]),1.0)
        self.assertEqual(info['audio_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())

    def test_cancel_callback_stops_between_native_steps(self):
        path=self.root/'s/in.wav';wav(path,b'\0\0'*16000)
        with self.assertRaises(VoiceError) as failure: self.asr.transcribe(path,lambda:True)
        self.assertEqual(failure.exception.code,'CANCELLED')

    def test_chinese_public_audio_independent_of_reference(self):
        manifest=ROOT/'data/c01_public/manifest.jsonl'
        self.assertTrue(manifest.exists(),'Public audio must exist; never skip real speech test')
        row=json.loads(manifest.read_text(encoding='utf-8').splitlines()[0])
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden during ASR')):
            result=self.asr.transcribe(ROOT/'data/c01_public'/row['audio_path'])
        self.assertEqual(result['audio_sha256'],row['audio_sha256'])
        self.assertTrue(any('\u4e00'<=c<='\u9fff' for c in result['text']))
        self.assertIsNone(result['confidence']);self.assertFalse(self.asr.metadata['hotwords_configured'])


class RealProcessTests(unittest.TestCase):
    def test_real_jsonl_reset_and_unconfigured_tts(self):
        rows=(ROOT/'data/c01_public/manifest.jsonl').read_text(encoding='utf-8').splitlines()
        row=json.loads(rows[0]);root=ROOT/'data/c01_public'
        with Client(root,asr_config=ROOT/'configs/asr.threads1.json') as client:
            hello=client.call('hello')
            self.assertEqual(hello['execution_kind'],'PC_REAL')
            self.assertTrue(hello['capabilities']['real_asr']);self.assertFalse(hello['capabilities']['real_tts'])
            self.assertFalse(hello['capabilities']['streaming_asr'])
            first=client.call('transcribe',session_id=row['recording_id'],language='zh',wav_path=row['audio_path'])
            reset=client.call('reset',session_id=row['recording_id'])
            second=client.call('transcribe',session_id=row['recording_id'],language='zh',wav_path=row['audio_path'])
            self.assertEqual(first['text'],second['text']);self.assertEqual(second['epoch'],reset['epoch'])
            self.assertTrue((root/row['audio_path']).exists())
            missing=client.call('synthesize',session_id=row['recording_id'],text='测试',output_dir=row['recording_id']+'/out')
            self.assertEqual(missing['code'],'MODEL_NOT_CONFIGURED')

    def test_real_cancel_discards_late_result_and_reset_recovers(self):
        with tempfile.TemporaryDirectory(prefix='voice-c01-cancel-') as temp:
            root=Path(temp);wav(root/'s/in.wav',b'\0\0'*16000*30)
            with Client(root,asr_config=ROOT/'configs/asr.threads1.json') as client:
                client.call('hello')
                rid=client.send('transcribe',session_id='s',language='zh',wav_path='s/in.wav')
                self.assertEqual(client.receive(rid,terminal=False)['event'],'accepted')
                cancel=client.call('cancel',target_request_id=rid)
                self.assertEqual(cancel['late_result_policy'],'DISCARD')
                self.assertEqual(cancel['stopped'],not cancel['cancel_pending'])
                with self.assertRaises(TimeoutError): client.receive(rid,timeout=.4)
                reset=client.call('reset',session_id='s')
                done=client.call('transcribe',session_id='s',language='zh',wav_path='s/in.wav')
                self.assertEqual(done['type'],'result');self.assertEqual(done['epoch'],reset['epoch'])


if __name__=='__main__': unittest.main()
