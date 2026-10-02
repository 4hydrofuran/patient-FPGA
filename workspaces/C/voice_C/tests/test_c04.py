import json
from pathlib import Path
import tempfile
import unittest
from voicec.audit import AuditLog
from voicec.client import Client


class AuditTests(unittest.TestCase):
    def test_rotation_bounded_and_payload_redacted(self):
        with tempfile.TemporaryDirectory(prefix='c04-audit-') as temp:
            root = Path(temp)/'private'
            log = AuditLog(root, max_bytes=256, backups=2)
            for i in range(100):
                log.write(dict(request_id=f'check-{i}', op='transcribe', type='result',
                    text='PRIVATE_SPOKEN_TEXT', wav_path='PRIVATE_AUDIO_PATH', session_id='PRIVATE_SPEAKER'))
            log.close()
            files = list(root.iterdir())
            self.assertLessEqual(len(files), 3)
            self.assertTrue((root/'worker.audit.jsonl.2').exists())
            for path in files:
                self.assertLessEqual(path.stat().st_size, 256)
                text = path.read_text('utf-8')
                self.assertNotIn('PRIVATE', text)
                for line in text.splitlines():
                    self.assertNotIn('text', json.loads(line))

    def test_existing_caller_directory_and_files_preserved(self):
        with tempfile.TemporaryDirectory(prefix='c04-caller-') as temp:
            root = Path(temp); p = root/'worker.audit.jsonl'; p.write_bytes(b'caller-data')
            with self.assertRaises(FileExistsError): AuditLog(root)
            self.assertEqual(p.read_bytes(), b'caller-data')

    def test_invalid_limits_rejected(self):
        for size in (True, 0, 1048577):
            with self.assertRaises(ValueError): AuditLog('unused', max_bytes=size)
        for count in (True, 0, 9):
            with self.assertRaises(ValueError): AuditLog('unused', backups=count)

    def test_real_subprocess_protocol_and_reset_cleanup_with_audit(self):
        # Contract waveform here; real ASR/TTS are measured in a separate run.
        with tempfile.TemporaryDirectory(prefix='c04-worker-') as temp:
            root = Path(temp); spool = root/'spool'; (spool/'s').mkdir(parents=True)
            caller = spool/'s/caller.bin'; caller.write_bytes(b'caller')
            with Client(spool, contract_tone=True, diagnostic_log=root/'audit') as c:
                self.assertEqual(c.call('hello')['type'], 'result')
                generated = c.call('synthesize', session_id='s', text='PRIVATE_TEST_SENTENCE', output_dir='s/out')
                output = spool/generated['wav_path']; self.assertTrue(output.exists())
                self.assertEqual(c.call('reset', session_id='s')['type'], 'result')
                self.assertFalse(output.exists()); self.assertEqual(caller.read_bytes(), b'caller')
            text = (root/'audit/worker.audit.jsonl').read_text('utf-8')
            self.assertNotIn('PRIVATE_TEST_SENTENCE', text)
            self.assertTrue(all(json.loads(x)['type'] in ('event','result','error') for x in text.splitlines()))
