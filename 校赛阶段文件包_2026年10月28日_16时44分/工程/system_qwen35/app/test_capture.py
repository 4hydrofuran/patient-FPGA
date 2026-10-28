"""CPU-only PCM/control tests; no mocked model, microphone or device claims."""
import os,struct,time,unittest
from .pc_audio import CaptureBuffer,PulseAudio
from .voice_cli import stop_enter_pending

class CaptureTests(unittest.TestCase):
    def test_no_early_ready(self):
        b=CaptureBuffer()
        with self.assertRaises(RuntimeError):b.announce_ready()
        self.assertIsNone(b.ready_announced_ns)
    def test_first_block_retained_and_callback_order(self):
        b=CaptureBuffer();raw=struct.pack('<h',1234)*3200;before=time.monotonic_ns()
        b.append(raw,before);seen=[]
        b.announce_ready(lambda:seen.append(b.pcm()))
        self.assertEqual(seen,[raw]);self.assertGreaterEqual(b.ready_announced_ns,b.first_chunk_ns)
        with self.assertRaises(RuntimeError):b.announce_ready()
    def test_exact_bytes_and_tail_preserved(self):
        b=CaptureBuffer();raw=struct.pack('<h',-123)*3200
        b.append(raw,1);b.append(bytes(6400),2)
        self.assertEqual(b.pcm(),raw+bytes(6400))
        self.assertEqual(b.diagnostics()['frames'],6400)
        self.assertEqual(b.diagnostics()['last_200ms_rms_fraction'],0)
    def test_duration_bound(self):
        b=CaptureBuffer(15)
        for n in range(75):b.append(bytes(6400),n)
        self.assertTrue(b.full);self.assertEqual(b.diagnostics()['duration_ms'],15000)
        with self.assertRaises(ValueError):b.append(bytes(6400),76)
    def test_invalid_duration(self):
        for value in (0,.1,16,True,float('inf'),float('nan'),'15'):
            with self.subTest(value=value),self.assertRaises(ValueError):CaptureBuffer(value)
    def test_format(self):
        for raw in (b'',bytes(6399),bytes(6402),'x'):
            with self.subTest(size=len(raw)),self.assertRaises(ValueError):CaptureBuffer().append(raw,1)
    def test_signal_statistics_not_confidence(self):
        b=CaptureBuffer();b.append(struct.pack('<hhhh',-32768,32767,0,0)*800,1)
        d=b.diagnostics();self.assertEqual(d['clipped_sample_count'],1600)
        self.assertEqual(d['peak_fraction'],1);self.assertEqual(d['zero_sample_fraction'],.5)
        self.assertNotIn('confidence',d)
    def test_empty_rejected(self):
        with self.assertRaises(ValueError):CaptureBuffer().diagnostics()
    def test_unauthorized_never_opens_device(self):
        # Authorization rejection executes before touching self.lib.
        with self.assertRaises(PermissionError):PulseAudio.record_push_to_talk(None,None,None)
    def test_input_poll_no_background_reader(self):
        r,w=os.pipe()
        with os.fdopen(r,'r') as reader,os.fdopen(w,'w') as writer:
            self.assertFalse(stop_enter_pending(reader))
            writer.write('\n');writer.flush();self.assertTrue(stop_enter_pending(reader))
            self.assertFalse(stop_enter_pending(reader))
            writer.write('YES\n');writer.flush()
            # After capture ends, the confirmation prompt remains sole reader.
            self.assertEqual(reader.readline(),'YES\n')
    def test_terminal_eof_is_cancel_not_confirmation(self):
        r,w=os.pipe();os.close(w)
        with os.fdopen(r,'r') as reader:
            with self.assertRaises(EOFError):stop_enter_pending(reader)

if __name__=='__main__':unittest.main(verbosity=2)
