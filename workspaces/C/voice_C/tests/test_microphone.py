"""Deterministic driver fixtures; these tests never open a physical microphone."""
import ctypes as ct
import hashlib
import struct
import unittest
from voicec.microphone import Microphone, WaveFormat, WaveHeader, pcm_format, _QUARANTINED


class FixtureDriver:
    def __init__(self, fail=None, malformed=False):
        self.fail, self.malformed = fail, malformed
        self.calls, self.queued = [], []
        self.started = False
        self.counter = 0

    def query(self, device):
        self.calls.append('query')

    def fill_next(self):
        header = self.queued.pop(0)
        self.counter += 1
        ct.memmove(header.data, struct.pack('<h', self.counter) * 3200, 6400)
        header.recorded = 3 if self.malformed else 6400
        header.flags |= 1

    def invoke(self, name, *args):
        self.calls.append(name)
        if name == self.fail:
            raise OSError('Fixture failure: ' + name)
        if name == 'waveInOpen':
            ct.cast(args[0], ct.POINTER(ct.c_void_p))[0] = ct.c_void_p(123)
        elif name in ('waveInPrepareHeader', 'waveInAddBuffer'):
            header = ct.cast(args[1], ct.POINTER(WaveHeader)).contents
            if name == 'waveInPrepareHeader':
                header.flags |= 2
            else:
                header.flags &= ~1
                header.recorded = 0
                self.queued.append(header)
                if self.started:
                    self.fill_next()
        elif name == 'waveInStart':
            self.started = True
            self.fill_next()


class MicrophoneTests(unittest.TestCase):
    def test_windows_abi_layout_and_format(self):
        self.assertEqual(ct.sizeof(WaveFormat), 18)
        self.assertEqual(ct.sizeof(WaveHeader), 48 if ct.sizeof(ct.c_void_p) == 8 else 32)
        fmt = pcm_format()
        self.assertEqual((fmt.tag, fmt.channels, fmt.rate, fmt.bytes_per_second,
                          fmt.alignment, fmt.bits, fmt.extra), (1, 1, 16000, 32000, 2, 16, 0))

    def test_invalid_capture_limits_rejected_before_device_access(self):
        for seconds in (True, float('nan'), float('inf'), 0, 61, '10'):
            with self.assertRaises(ValueError):
                Microphone(seconds=seconds)
        for device in (True, -1, '0'):
            with self.assertRaises(ValueError):
                Microphone(device=device)
        for bound in (True, 0, 65):
            with self.assertRaises(ValueError):
                Microphone(queue_chunks=bound)

    def test_exact_order_pcm_hash_and_release(self):
        driver = FixtureDriver()
        with Microphone(seconds=0.4, backend=driver) as mic:
            chunks = list(mic)
        raw = b''.join(x['pcm'] for x in chunks)
        self.assertEqual([x['seq'] for x in chunks], [0, 1])
        self.assertEqual(raw, struct.pack('<h', 1) * 3200 + struct.pack('<h', 2) * 3200)
        self.assertEqual(mic.stats['pcm_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(mic.stats['frames'], 6400)
        self.assertTrue(mic.stats['released'])
        self.assertEqual(driver.calls.count('waveInUnprepareHeader'), 16)
        self.assertLess(driver.calls.index('waveInReset'), driver.calls.index('waveInClose'))

    def test_non_200ms_final_chunk_has_only_requested_frames(self):
        with Microphone(seconds=0.25, backend=FixtureDriver()) as mic:
            chunks = list(mic)
        self.assertEqual([len(x['pcm']) // 2 for x in chunks], [3200, 800])
        self.assertEqual(mic.stats['frames'], 4000)

    def test_queue_overflow_aborts_and_releases(self):
        mic = Microphone(seconds=1, queue_chunks=1, backend=FixtureDriver())
        try:
            # Producer intentionally runs without a consumer until completion.
            mic.start()
            self.assertTrue(mic.done.wait(2))
            with self.assertRaises(BufferError):
                list(mic)
        except BufferError:
            pass  # Startup can already observe the deterministic overflow.
        finally:
            mic.close()
        self.assertTrue(mic.stats['queue_overrun'])
        self.assertTrue(mic.stats['released'])
        self.assertEqual(mic.stats['chunks'], 1)

    def test_open_failure_is_not_reported_as_recording(self):
        mic = Microphone(seconds=0.2, backend=FixtureDriver(fail='waveInOpen'))
        with self.assertRaises(OSError):
            mic.start()
        self.assertFalse(mic.stats['opened'])
        self.assertFalse(mic.stats['started'])
        self.assertEqual(mic.stats['frames'], 0)

    def test_prepare_failure_cleans_only_prepared_headers(self):
        driver = FixtureDriver(fail='waveInPrepareHeader')
        mic = Microphone(seconds=0.2, backend=driver)
        with self.assertRaises(OSError):
            mic.start()
        self.assertTrue(mic.stats['released'])
        self.assertNotIn('waveInUnprepareHeader', driver.calls)

    def test_malformed_driver_bytes_abort_and_release(self):
        mic = Microphone(seconds=0.2, backend=FixtureDriver(malformed=True))
        try:
            with self.assertRaises(OSError):
                with mic:
                    list(mic)
        finally:
            mic.close()
        self.assertTrue(mic.stats['released'])
        self.assertEqual(mic.stats['frames'], 0)

    def test_release_failure_keeps_buffers_alive_and_is_error(self):
        before = len(_QUARANTINED)
        mic = Microphone(seconds=0.2, backend=FixtureDriver(fail='waveInReset'))
        try:
            with self.assertRaises(OSError):
                with mic:
                    list(mic)
            self.assertFalse(mic.stats['released'])
            self.assertEqual(len(_QUARANTINED), before + 1)
            self.assertTrue(mic.stats['cleanup_errors'])
        finally:
            # Fixture only: no native device can reference this fake handle.
            del _QUARANTINED[before:]

    def test_read_before_start_and_restart_rejected(self):
        mic = Microphone(seconds=0.2, backend=FixtureDriver())
        with self.assertRaises(RuntimeError):
            list(mic)
        with mic:
            list(mic)
        with self.assertRaises(RuntimeError):
            mic.start()


if __name__ == '__main__':
    unittest.main()
