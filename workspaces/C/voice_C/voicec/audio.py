"""Bounded WAV validation and exclusive synthetic tone generation."""
import array
import hashlib
import io
import math
import os
import sys
import wave

MAX_WAV_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 60


class VoiceError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def read_pcm16(path, asr=False):
    if path.stat().st_size > MAX_WAV_BYTES:
        raise VoiceError('AUDIO_TOO_LARGE', 'WAV exceeds configured byte limit')
    with path.open('rb') as f:
        raw = f.read(MAX_WAV_BYTES + 1)
    if len(raw) > MAX_WAV_BYTES:
        raise VoiceError('AUDIO_TOO_LARGE', 'WAV exceeds configured byte limit')
    try:
        with wave.open(io.BytesIO(raw), 'rb') as w:
            rate, frames = w.getframerate(), w.getnframes()
            if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getcomptype() != 'NONE':
                raise VoiceError('BAD_AUDIO_FORMAT', 'Require mono PCM16 WAV')
            if rate <= 0 or (asr and rate != 16000):
                raise VoiceError('BAD_SAMPLE_RATE', 'ASR requires 16000 Hz')
            if frames <= 0 or frames / rate > MAX_AUDIO_SECONDS:
                raise VoiceError('BAD_AUDIO_DURATION', 'Require nonempty audio within duration limit')
            pcm = w.readframes(frames)
            if len(pcm) != frames * 2:
                raise VoiceError('TRUNCATED_AUDIO', 'WAV frame data is truncated')
    except (wave.Error, EOFError) as exc:
        raise VoiceError('BAD_WAV', 'Invalid PCM WAV container') from exc
    samples = array.array('h', pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    info = dict(sample_rate=rate, frames=frames, audio_duration_ms=frames / rate * 1000,
                audio_sha256=hashlib.sha256(raw).hexdigest(),
                silent=all(v == 0 for v in samples),
                clipped_samples=sum(v in (-32768, 32767) for v in samples))
    return info, pcm


def inspect_wav(path, asr=False):
    return read_pcm16(path, asr)[0]


def write_tone(path, duration_ms=120, sample_rate=16000):
    """Not speech; opt-in protocol fixture only. Never derived from reference text."""
    frames = round(sample_rate * duration_ms / 1000)
    pcm = array.array('h', [round(1000 * math.sin(2 * math.pi * 440 * i / sample_rate))
                            for i in range(frames)])
    if sys.byteorder != 'little':
        pcm.byteswap()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as f:
        with wave.open(f, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm.tobytes())
    return dict(sample_rate=sample_rate, frames=frames)


def write_speech(path, samples, sample_rate):
    """Native float waveform to PCM16; fixed gain, no AGC, never overwrite."""
    import numpy as np
    data = np.asarray(samples)
    if type(sample_rate) is not int or sample_rate != 22050:
        raise VoiceError('BAD_TTS_RATE', 'Require native 22050 Hz')
    if data.ndim != 1 or not 0 < len(data) <= sample_rate * MAX_AUDIO_SECONDS:
        raise VoiceError('BAD_TTS_WAVEFORM', 'Require bounded nonempty mono waveform')
    if not np.issubdtype(data.dtype, np.number) or np.iscomplexobj(data) or not np.all(np.isfinite(data)):
        raise VoiceError('BAD_TTS_WAVEFORM', 'Require finite real samples')
    scaled = np.rint(data.astype(np.float64) * 32768.0)
    out_of_range = int(np.count_nonzero((scaled < -32768) | (scaled > 32767)))
    pcm = np.clip(scaled, -32768, 32767).astype('<i2')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as f:
            with wave.open(f, 'wb') as w:
                w.setparams((1, 2, sample_rate, 0, 'NONE', 'not compressed'))
                w.writeframes(pcm.tobytes())
        result = inspect_wav(path)
        if result['silent']:
            raise VoiceError('EMPTY_TTS_SPEECH', 'Native output rounded to silence')
    except Exception:
        # O_EXCL succeeded: only this call's newly created file is removed.
        path.unlink(missing_ok=True)
        raise
    return result | dict(float_out_of_range_samples=out_of_range,
        amplitude_policy='FIXED_GAIN_1_ROUND_TIES_EVEN_CLAMP_PCM16_NO_AGC_NO_TRIM',
        peak_abs_float=float(np.max(np.abs(data))), rms_float=float(np.sqrt(np.mean(data.astype(float)**2))))
