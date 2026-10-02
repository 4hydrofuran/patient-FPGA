import hashlib
import json
import os
import queue
import subprocess
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from voicec.audio import VoiceError, inspect_wav, write_tone
from voicec.client import Client
from voicec.dataset import validate_plan
from voicec.memory import memory_snapshot
from voicec.metrics import aggregate, cer, listening_report, literal_key_items, normalize, timing
from voicec.spool import Spool
from voicec.worker import MAX_LINE, Worker

ROOT = Path(__file__).resolve().parents[1]


def make_wav(path, rate=16000, channels=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setparams((channels, 2, rate, 0, 'NONE', 'not compressed'))
        w.writeframes(b'\0\0' * 320 * channels)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='voice-c00-test-')
        self.root = Path(self.tmp.name)
        make_wav(self.root/'s1/in.wav')
        self.messages = queue.Queue()
        self.worker = Worker(self.root, self.messages.put, contract_tone=True, test_delay_ms=80)
        self.seq = 0

    def tearDown(self):
        self.worker.close()
        self.tmp.cleanup()

    def send(self, op, **fields):
        self.seq += 1
        r = dict(api_version=1, request_id=f'r{self.seq}', op=op, **fields)
        self.worker.handle(r)
        return r['request_id']

    def receive(self, rid, terminal=True):
        end = time.monotonic()+3
        while time.monotonic()<end:
            item = self.messages.get(timeout=3)
            if item['request_id']==rid and (not terminal or item['type']!='event'):
                return item
        self.fail('No expected response')

    def error(self, op, code, **fields):
        self.assertEqual(self.receive(self.send(op, **fields))['code'], code)

    def test_hello_truthful_capabilities(self):
        r = self.receive(self.send('hello'))
        self.assertEqual(r['execution_kind'], 'CONTRACT_TEST')
        self.assertFalse(r['capabilities']['real_asr'])
        self.assertFalse(r['capabilities']['real_tts'])
        self.assertFalse(r['capabilities']['streaming_asr'])
        self.assertEqual(r['models'], [])

    def test_valid_wav_does_not_return_fake_transcript(self):
        r = self.receive(self.send('transcribe', session_id='s1', wav_path='s1/in.wav', language='zh'))
        self.assertEqual(r['code'], 'MODEL_NOT_CONFIGURED')
        self.assertIsNone(r['text'])
        self.assertIsNone(r['confidence'])
        self.assertTrue(r['silent'])
        self.assertEqual(r['audio_duration_ms'], 20)

    def test_tone_explicit_not_speech_and_text_hash(self):
        text = '$(DoNotExecute)；否定测试。'
        r = self.receive(self.send('synthesize', session_id='s1', text=text, output_dir='s1/out'))
        self.assertEqual(r['output_kind'], 'NON_SPEECH_TEST_TONE')
        self.assertEqual(r['text_sha256'], hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(inspect_wav(self.root/r['wav_path'])['frames'], r['frames'])
        self.assertIsNone(r['audible_ms'])

    def test_reset_only_deletes_owned_outputs(self):
        a = self.receive(self.send('synthesize', session_id='s1', text='测试', output_dir='s1/out'))
        b = self.receive(self.send('synthesize', session_id='s2', text='测试', output_dir='s2/out'))
        marker = self.root/'s1/out/caller.txt'
        marker.write_text('caller-owned')
        r = self.receive(self.send('reset', session_id='s1'))
        self.assertEqual(r['epoch'], 1)
        self.assertFalse((self.root/a['wav_path']).exists())
        self.assertTrue((self.root/b['wav_path']).exists())
        self.assertTrue((self.root/'s1/in.wav').exists())
        self.assertTrue(marker.exists())

    def wait_running(self, rid):
        end = time.monotonic()+2
        while time.monotonic()<end:
            with self.worker.lock:
                if self.worker.jobs[rid]['started']:
                    return
            time.sleep(.001)
        self.fail('Job did not start')

    def test_running_cancel_pending_discards_late_output(self):
        rid = self.send('synthesize', session_id='s1', text='测试', output_dir='s1/out')
        self.receive(rid, terminal=False)
        self.wait_running(rid)
        r = self.receive(self.send('cancel', target_request_id=rid))
        self.assertTrue(r['cancel_pending'])
        self.assertFalse(r['stopped'])
        self.worker.tasks.join()
        self.assertTrue(self.messages.empty())
        self.assertEqual(list(self.root.rglob('*.wav')), [self.root/'s1/in.wav'])

    def test_reset_discards_old_epoch_job(self):
        rid = self.send('synthesize', session_id='s1', text='旧结果', output_dir='s1/out')
        self.receive(rid, terminal=False)
        self.wait_running(rid)
        r = self.receive(self.send('reset', session_id='s1'))
        self.assertTrue(r['pending_compute'])
        self.worker.tasks.join()
        self.assertTrue(self.messages.empty())
        newer = self.receive(self.send('synthesize', session_id='s1', text='新结果', output_dir='s1/out'))
        self.assertEqual(newer['epoch'], 1)

    def test_bounded_queue(self):
        first = self.send('synthesize', session_id='s1', text='一', output_dir='s1/out')
        self.receive(first, terminal=False)
        self.wait_running(first)
        for text in ['二', '三']:
            rid = self.send('synthesize', session_id='s1', text=text, output_dir='s1/out')
            self.receive(rid, terminal=False)
        self.error('synthesize', 'BUSY', session_id='s1', text='四', output_dir='s1/out')

    def test_duplicate_id(self):
        self.worker.handle(dict(api_version=1, request_id='same', op='hello'))
        self.receive('same')
        self.worker.handle(dict(api_version=1, request_id='same', op='hello'))
        self.assertEqual(self.receive('same')['code'], 'DUPLICATE_ID')

    def test_bad_version_and_extra_fields(self):
        self.worker.handle(dict(api_version=True, request_id='bad', op='hello'))
        self.assertEqual(self.receive('bad')['code'], 'BAD_VERSION')
        self.error('hello', 'BAD_FIELDS', backend='shell')

    def test_optional_streaming_is_rejected(self):
        self.error('asr_begin', 'UNSUPPORTED_OP')

    def test_paths_reject_escape_absolute_unc_and_ads(self):
        for path in ['../s1/in.wav', '/s1/in.wav', 'C:/secret.wav', '\\\\host\\file.wav',
                     's1/in.wav:ads', 's1//in.wav', 's1/./in.wav', 's1/NUL.wav',
                     's1/name.', 's1/name ', 's1/COM1']:
            with self.subTest(path=path):
                self.error('transcribe', 'UNSAFE_PATH', session_id='s1', language='zh', wav_path=path)

    def test_cross_session_path_and_missing_file(self):
        self.error('transcribe', 'CROSS_SESSION_PATH', session_id='s2', language='zh', wav_path='s1/in.wav')
        self.error('transcribe', 'FILE_NOT_FOUND', session_id='s1', language='zh', wav_path='s1/missing.wav')

    def test_audio_sample_rate_stereo_and_corrupt(self):
        for name, rate, channels, code in [('low.wav',8000,1,'BAD_SAMPLE_RATE'), ('stereo.wav',16000,2,'BAD_AUDIO_FORMAT')]:
            make_wav(self.root/'s1'/name, rate, channels)
            self.error('transcribe', code, session_id='s1', language='zh', wav_path='s1/'+name)
        (self.root/'s1/bad.wav').write_bytes(b'not a wav')
        self.error('transcribe', 'BAD_WAV', session_id='s1', language='zh', wav_path='s1/bad.wav')

    def test_invalid_and_oversized_text(self):
        for text in ['', ' ', 'x'*2049, '\x00']:
            self.error('synthesize', 'BAD_TEXT', session_id='s1', text=text, output_dir='s1/out')

    def test_cancel_missing_target(self):
        self.error('cancel', 'TARGET_NOT_ACTIVE', target_request_id='absent')


class SpoolAndAudioTests(unittest.TestCase):
    def test_actual_link_or_windows_junction_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'s').mkdir()
            (root/'other').mkdir()
            (root/'other/marker.txt').write_text('must survive')
            link=root/'s/link'
            try:
                link.symlink_to(root/'other', target_is_directory=True)
            except OSError:
                if os.name != 'nt':
                    raise
                # Native PowerShell, fixed command and environment paths; no elevation.
                r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
                    'New-Item -ItemType Junction -Path $env:VOICE_C_TEST_LINK -Target $env:VOICE_C_TEST_TARGET -ErrorAction Stop | Out-Null'],
                    env=os.environ|{'VOICE_C_TEST_LINK':str(link),'VOICE_C_TEST_TARGET':str(root/'other')},
                    capture_output=True,timeout=10)
                self.assertEqual(r.returncode,0,'Actual junction fixture creation failed')
            try:
                with self.assertRaises(VoiceError):
                    Spool(root).resolve('s/link/x.wav', 's')
            finally:
                # Remove only this checked link inside the private test directory.
                self.assertTrue(link.parent.resolve().is_relative_to(root.resolve()))
                link.rmdir() if os.name=='nt' or not link.is_symlink() else link.unlink()
            self.assertTrue((root/'other/marker.txt').exists())

    def test_windows_reparse_attribute_rejected(self):
        with patch('voicec.spool.os.lstat') as stat:
            stat.return_value.st_file_attributes=0x400
            with patch('pathlib.Path.is_symlink', return_value=False):
                self.assertTrue(Spool.is_link(Path('junction')))

    def test_truncated_pcm(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.wav'
            make_wav(p)
            p.write_bytes(p.read_bytes()[:-20])
            with self.assertRaises(VoiceError) as caught:
                inspect_wav(p, asr=True)
            self.assertEqual(caught.exception.code,'TRUNCATED_AUDIO')

    def test_tone_cannot_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.wav'
            p.write_bytes(b'caller-owned')
            with self.assertRaises(FileExistsError):
                write_tone(p)
            self.assertEqual(p.read_bytes(),b'caller-owned')


class ProcessTests(unittest.TestCase):
    def test_persistent_client_and_disabled_tts(self):
        with tempfile.TemporaryDirectory() as tmp, Client(tmp) as c:
            pid=c.process.pid
            for _ in range(3):
                self.assertEqual(c.call('hello')['type'],'result')
            self.assertEqual(pid,c.process.pid)
            self.assertEqual(c.call('synthesize',session_id='s',text='测试',output_dir='s/out')['code'],'MODEL_NOT_CONFIGURED')
            self.assertEqual(c.stderr,[])

    def test_bad_json_nonfinite_duplicate_keys_and_utf8_recover(self):
        with tempfile.TemporaryDirectory() as tmp, Client(tmp) as c:
            for raw in [b'{\n',b'{"api_version":NaN}\n',b'{"op":"hello","op":"reset"}\n',b'\xff\n']:
                c.process.stdin.buffer.write(raw)
                c.process.stdin.buffer.flush()
                self.assertEqual(c.receive(None)['code'],'BAD_JSON')
                self.assertEqual(c.call('hello')['type'],'result')

    def test_oversized_jsonl_drained_and_recovers(self):
        with tempfile.TemporaryDirectory() as tmp, Client(tmp) as c:
            c.process.stdin.write('x'*(MAX_LINE+100)+'\n')
            c.process.stdin.flush()
            self.assertEqual(c.receive(None)['code'],'LINE_TOO_LARGE')
            self.assertEqual(c.call('hello')['type'],'result')

    def test_memory_is_actual_process_peak_or_explicit_unknown(self):
        r=memory_snapshot()
        self.assertEqual(r['memory_scope'],'WORKER_PROCESS_LIFETIME_PEAK')
        if r['peak_rss_bytes'] is not None:
            self.assertGreater(r['peak_rss_bytes'],0)
        else:
            self.assertEqual(r['memory_method'],'UNAVAILABLE')


class MetricAndPlanTests(unittest.TestCase):
    def test_cer_substitution_deletion_insertion(self):
        self.assertEqual(cer('三','四')['substitutions'],1)
        self.assertEqual(cer('没有发热','有发热')['deletions'],1)
        self.assertEqual(cer('去','去吧')['insertions'],1)
        self.assertEqual(cer('你好，世界。','你好世界')['errors'],0)

    def test_empty_reference_and_decimal_preservation(self):
        self.assertIsNone(cer('','多余')['cer'])
        self.assertGreater(cer('零点五，0.5','零点五，5')['errors'],0)
        self.assertEqual(normalize('负数 -２，１２％'), '负数-2１２%'.replace('１２','12'))

    def test_literal_key_counts_not_semantic_claim(self):
        r=literal_key_items('我没有喝水','我喝水',[{'kind':'negation','text':'没有'}])
        self.assertEqual(r['failed_items'],1)
        self.assertEqual(r['semantic_negation_correctness'],'HUMAN_REVIEW_REQUIRED')

    def test_timing_units_and_invalid_numbers(self):
        r=timing(100,500,150,1024)
        self.assertEqual(r['rtf'],.2)
        self.assertIsNone(r['audible_ms'])
        for bad in [float('nan'),float('inf'),-1,True]:
            with self.assertRaises(ValueError):
                timing(bad,500)

    def target(self):
        return dict(recording_id='m',reference_text='你好',key_items=[],audio_sha256='a'*64,
                    authorization_status='PENDING',consent_reference=None,transcript_status='PENDING',transcript_reviewer_id=None)

    def result(self):
        return dict(recording_id='m',text='你好',audio_sha256='a'*64,execution_kind='CONTRACT_TEST',
                    status='SUCCESS',compute_ms=10,audio_duration_ms=100)

    def test_no_results_is_not_quality_measurement(self):
        r=aggregate([self.target()],[])
        self.assertEqual(r['status'],'NOT_TESTED')
        self.assertIsNone(r['full_set_cer'])
        self.assertEqual(r['missing'],1)

    def test_fixture_rejected_for_real_and_marked_if_allowed(self):
        with self.assertRaises(ValueError):
            aggregate([self.target()],[self.result()])
        r=aggregate([self.target()],[self.result()],allow_contract=True)
        self.assertEqual(r['status'],'CONTRACT_METRIC_TEST_ONLY')
        self.assertFalse(r['model_quality_claim'])

    def test_real_results_require_authorization_and_review(self):
        result=self.result()|{'execution_kind':'PC_REAL'}
        with self.assertRaises(ValueError):
            aggregate([self.target()],[result])

    def test_missing_difficult_item_leaves_full_cer_unknown(self):
        second=self.target()|{'recording_id':'n'}
        r=aggregate([self.target(),second],[self.result()],allow_contract=True)
        self.assertIsNone(r['full_set_cer'])
        self.assertEqual(r['observed_coverage'],.5)

    def test_hash_mismatch_and_duplicate_results(self):
        with self.assertRaises(ValueError):
            aggregate([self.target()],[self.result()|{'audio_sha256':'b'*64}],True)
        with self.assertRaises(ValueError):
            aggregate([self.target()],[self.result(),self.result()],True)

    def test_48_planned_not_collected(self):
        rows=[json.loads(s) for s in (ROOT/'data/recording_plan.jsonl').read_text(encoding='utf-8').splitlines()]
        r=validate_plan(rows)
        self.assertEqual((r['dev'],r['test'],r['collected']),(24,24,0))
        with self.assertRaises(ValueError):
            validate_plan(rows,require_recordings=True)

    def test_speaker_overlap_is_rejected(self):
        rows=[json.loads(s) for s in (ROOT/'data/recording_plan.jsonl').read_text(encoding='utf-8').splitlines()]
        rows[0]['speaker_id']=rows[-1]['speaker_id']='same-person'
        with self.assertRaisesRegex(ValueError,'speakers'):
            validate_plan(rows)

    def test_blind_listening_is_empty_not_fake_scores(self):
        rows=[json.loads(s) for s in (ROOT/'data/tts_listening.template.jsonl').read_text(encoding='utf-8').splitlines()]
        r=listening_report(rows)
        self.assertEqual((r['status'],r['reviewed'],r['pending']),('NOT_TESTED',0,12))
        self.assertIsNone(r['intelligibility'])


if __name__=='__main__':
    unittest.main()
