"""Bounded mono 22050 -> stereo 48000 PCM16 file conversion, no playback."""
import math
from pathlib import Path
import wave

import numpy as np
from scipy.signal import resample_poly

INPUT_RATE = 22050
OUTPUT_RATE = 48000
MAX_SECONDS = 30


def float_mono(samples):
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim != 1 or not 0 < len(x) <= INPUT_RATE * MAX_SECONDS:
        raise ValueError('expected nonempty mono audio, at most 30 seconds')
    if not np.isfinite(x).all():
        raise ValueError('nonfinite audio')
    if np.max(np.abs(x)) > 1:
        raise ValueError('source audio outside normalized range; do not silently clip')
    return x


def convert(samples, rate=INPUT_RATE, gain_db=-30.0):
    if type(rate) is not int or rate != INPUT_RATE:
        raise ValueError('this fixed conversion requires 22050Hz input')
    if not math.isfinite(gain_db) or not -90 <= gain_db <= 0:
        raise ValueError('gain must be finite and between -90 and 0dB')
    x = float_mono(samples)
    # gcd(22050,48000)=150, so the exact rational ratio is 320/147.
    y = resample_poly(x, 320, 147, window=('kaiser', 5.0), padtype='constant')
    if len(y) != (len(x) * 320 + 146) // 147 or not np.isfinite(y).all():
        raise ValueError('resampler length/finite contract failed')
    gain = 10 ** (gain_db / 20)
    y *= gain
    # FIR boundary overshoot is handled explicitly, not hidden clipping. This
    # file scaling is NOT an electrical current limiter or playback permission.
    peak_before = float(np.max(np.abs(y)))
    headroom_scale = min(1.0, 0.999 / peak_before) if peak_before else 1.0
    y *= headroom_scale
    mono = np.rint(y * 32767).astype('<i2')
    stereo = np.column_stack([mono, mono]).astype('<i2', copy=False)
    return stereo, {'input_rate_hz': INPUT_RATE, 'output_rate_hz': OUTPUT_RATE,
                    'input_frames': len(x), 'output_frames': len(stereo),
                    'ratio_up': 320, 'ratio_down': 147,
                    'gain_db': gain_db, 'boundary_headroom_scale': headroom_scale,
                    'channels': 2, 'encoding': 'PCM_S16LE',
                    'playback_attempted': False, 'audible_onset_ms': None,
                    'current_limit_proof': False}


def write_pcm16(path, data, rate):
    path = Path(path)
    if path.is_symlink() or path.exists():
        raise FileExistsError('output already exists')
    a = np.asarray(data)
    if a.dtype != np.dtype('<i2') or a.ndim not in [1, 2] or not len(a):
        raise ValueError('expected nonempty PCM16 mono/stereo array')
    channels = 1 if a.ndim == 1 else a.shape[1]
    if channels not in [1, 2] or rate not in [INPUT_RATE, OUTPUT_RATE]:
        raise ValueError('unsupported WAV format')
    with path.open('xb') as stream:
        with wave.open(stream, 'wb') as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(a.tobytes())


def read_mono(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('regular input file required')
    with wave.open(str(path), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, INPUT_RATE, 'NONE'):
            raise ValueError('expected mono PCM16 WAV at 22050Hz')
        count = wav.getnframes()
        if not 0 < count <= INPUT_RATE * MAX_SECONDS:
            raise ValueError('WAV length outside bounds')
        raw = wav.readframes(count)
        if len(raw) != count * 2:
            raise ValueError('truncated WAV')
    return np.frombuffer(raw, dtype='<i2').astype(np.float64) / 32768
