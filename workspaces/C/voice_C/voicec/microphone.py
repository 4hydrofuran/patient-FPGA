"""Windows local capture adapter. No microphone access on import or enumeration.

Capture belongs to the independent client, never to the SP_VOICE_V1 worker.
WinMM returns actual 16 kHz mono PCM16; no VAD, AGC or resampling here.
"""
import ctypes as ct
import hashlib
import math
import os
import queue
import threading
import time

WORD = ct.c_uint16
DWORD = ct.c_uint32
UINT_PTR = ct.c_size_t


class WaveFormat(ct.Structure):
    _pack_ = 2
    _fields_ = [('tag', WORD), ('channels', WORD), ('rate', DWORD),
                ('bytes_per_second', DWORD), ('alignment', WORD),
                ('bits', WORD), ('extra', WORD)]


class WaveHeader(ct.Structure):
    _fields_ = [('data', ct.c_void_p), ('length', DWORD), ('recorded', DWORD),
                ('user', UINT_PTR), ('flags', DWORD), ('loops', DWORD),
                ('next', ct.c_void_p), ('reserved', UINT_PTR)]


class WaveCaps(ct.Structure):
    _fields_ = [('mid', WORD), ('pid', WORD), ('version', DWORD),
                ('name', ct.c_wchar * 32), ('formats', DWORD),
                ('channels', WORD), ('reserved', WORD)]


def pcm_format():
    return WaveFormat(1, 1, 16000, 32000, 2, 16, 0)


class WinMM:
    def __init__(self):
        if os.name != 'nt':
            raise OSError('This capture adapter requires Windows')
        self.dll = ct.WinDLL('winmm')
        signatures = {
            'waveInGetNumDevs': ([], DWORD),
            'waveInGetDevCapsW': ([UINT_PTR, ct.POINTER(WaveCaps), DWORD], DWORD),
            'waveInGetErrorTextW': ([DWORD, ct.c_wchar_p, DWORD], DWORD),
            'waveInOpen': ([ct.POINTER(ct.c_void_p), DWORD, ct.POINTER(WaveFormat),
                            UINT_PTR, UINT_PTR, DWORD], DWORD),
        }
        for name in ('waveInPrepareHeader', 'waveInAddBuffer', 'waveInUnprepareHeader'):
            signatures[name] = ([ct.c_void_p, ct.POINTER(WaveHeader), DWORD], DWORD)
        for name in ('waveInStart', 'waveInStop', 'waveInReset', 'waveInClose'):
            signatures[name] = ([ct.c_void_p], DWORD)
        for name, (args, result) in signatures.items():
            fn = getattr(self.dll, name)
            fn.argtypes, fn.restype = args, result

    def invoke(self, name, *args):
        code = int(getattr(self.dll, name)(*args))
        if code:
            text = ct.create_unicode_buffer(256)
            self.dll.waveInGetErrorTextW(code, text, len(text))
            raise OSError(f'{name}: MMRESULT={code}: {text.value}')

    def devices(self):
        result = []
        for device in range(self.dll.waveInGetNumDevs()):
            caps = WaveCaps()
            self.invoke('waveInGetDevCapsW', device, ct.byref(caps), ct.sizeof(caps))
            result.append(dict(id=device, name=caps.name, max_channels=int(caps.channels)))
        return result

    def query(self, device):
        fmt = pcm_format()
        # WAVE_FORMAT_QUERY: checks format; does not open or record.
        self.invoke('waveInOpen', None, device, ct.byref(fmt), 0, 0, 1)


# Keep Python buffers alive if a broken driver refuses reset/unprepare/close.
# They cannot safely be freed while the driver might still reference them.
_QUARANTINED = []


class Microphone:
    def __init__(self, device=0, seconds=10, queue_chunks=32, backend=None):
        if type(device) is not int or device < 0:
            raise ValueError('device must be a nonnegative integer')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0.2 <= seconds <= 60:
            raise ValueError('seconds must be finite, between 0.2 and 60')
        if type(queue_chunks) is not int or not 1 <= queue_chunks <= 64:
            raise ValueError('queue_chunks must be 1..64')
        self.device, self.seconds = device, seconds
        self.target_frames = round(seconds * 16000)
        self.backend = backend or WinMM()
        self.queue = queue.Queue(maxsize=queue_chunks)
        self.stop = threading.Event()
        self.done = threading.Event()
        self.ready = threading.Event()
        self.thread = None
        self.error = None
        self.stats = dict(opened=False, started=False, released=False, frames=0, chunks=0,
                          queue_high_water=0, queue_overrun=False, native_buffer_starvation=False,
                          capture_start_monotonic=None, capture_stop_monotonic=None)

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Capture is single use')
        self.thread = threading.Thread(target=self._capture, name='voicec-local-mic', daemon=True)
        self.thread.start()
        if not self.ready.wait(5):
            self.close()
            raise TimeoutError('Microphone startup timed out')
        if self.error:
            self.close()
            raise self.error
        return self

    def _offer(self, raw):
        if not raw or len(raw) > 6400 or len(raw) % 2:
            raise OSError('Driver returned invalid PCM buffer length')
        item = dict(pcm=raw, seq=self.stats['chunks'], available_monotonic=time.perf_counter())
        try:
            self.queue.put_nowait(item)
        except queue.Full as exc:
            self.stats['queue_overrun'] = True
            raise BufferError('Microphone queue full; abort rather than silently drop audio') from exc
        self.stats['frames'] += len(raw) // 2
        self.stats['chunks'] += 1
        self.stats['queue_high_water'] = max(self.stats['queue_high_water'], self.queue.qsize())

    def _capture(self):
        api, handle = self.backend, ct.c_void_p()
        prepared, buffers = [], []
        digest = hashlib.sha256()
        try:
            api.query(self.device)
            fmt = pcm_format()
            api.invoke('waveInOpen', ct.byref(handle), self.device, ct.byref(fmt), 0, 0, 0)
            self.stats['opened'] = True
            # Sixteen native buffers (3.2 s); distinct Python queue (<=12.8 s).
            for _ in range(16):
                data = ct.create_string_buffer(6400)
                header = WaveHeader(data=ct.addressof(data), length=6400)
                buffers.append((data, header))
                api.invoke('waveInPrepareHeader', handle, ct.byref(header), ct.sizeof(header))
                prepared.append((data, header))
                api.invoke('waveInAddBuffer', handle, ct.byref(header), ct.sizeof(header))
            api.invoke('waveInStart', handle)
            self.stats['started'] = True
            start = time.perf_counter()
            self.stats['capture_start_monotonic'] = start
            self.ready.set()
            cursor = 0
            while not self.stop.is_set() and self.stats['frames'] < self.target_frames:
                if time.perf_counter() - start > self.seconds + 3:
                    raise TimeoutError('Device did not deliver the requested frames within duration + 3 s')
                data, header = buffers[cursor]
                if not header.flags & 1:  # WHDR_DONE, CALLBACK_NULL polling
                    self.stop.wait(0.005)
                    continue
                if all(h.flags & 1 for _, h in buffers):
                    self.stats['native_buffer_starvation'] = True
                    raise BufferError('All native buffers exhausted; continuous capture cannot be asserted')
                count = int(header.recorded)
                if count <= 0 or count > 6400 or count % 2:
                    raise OSError('Driver returned invalid dwBytesRecorded')
                remaining = (self.target_frames - self.stats['frames']) * 2
                raw = data.raw[:min(count, remaining)]
                self._offer(raw)
                digest.update(raw)
                if self.stats['frames'] < self.target_frames:
                    api.invoke('waveInAddBuffer', handle, ct.byref(header), ct.sizeof(header))
                cursor = (cursor + 1) % len(buffers)
            self.stats['pcm_sha256'] = digest.hexdigest()
        except Exception as exc:
            self.error = exc
        finally:
            self.stats['capture_stop_monotonic'] = time.perf_counter() if self.stats['started'] else None
            cleanup_errors = []
            if self.stats['opened']:
                try:
                    # Reset stops recording and returns all queued driver buffers.
                    api.invoke('waveInReset', handle)
                    for _, header in prepared:
                        api.invoke('waveInUnprepareHeader', handle, ct.byref(header), ct.sizeof(header))
                    api.invoke('waveInClose', handle)
                    self.stats['released'] = True
                except Exception as exc:
                    cleanup_errors.append(str(exc))
                    _QUARANTINED.append((api, handle, buffers))
                    if not self.error:
                        self.error = exc
            self.stats['cleanup_errors'] = cleanup_errors
            self.ready.set()
            self.done.set()

    def __iter__(self):
        if self.thread is None:
            raise RuntimeError('Call start before reading microphone chunks')
        while True:
            if self.error:
                raise self.error
            try:
                yield self.queue.get(timeout=0.1)
            except queue.Empty:
                if self.done.is_set():
                    if self.error:
                        raise self.error
                    return

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise TimeoutError('Capture thread did not stop; device release is unconfirmed')

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()
