"""PC converter/architecture tests; never invoke an audio device or a board."""
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from modules.voice_A.file_tts.pcm import convert, read_mono, write_pcm16
from clock_model import codec_plan, oversampling_budget, require_device_paced_stream, require_noncontending_profile


class ConverterTests(unittest.TestCase):
    def test_exact_ratio_and_duration(self):
        for count in [1, 17, 147, 22050, 65280]:
            with self.subTest(count=count):
                out, meta = convert(np.zeros(count))
                self.assertEqual(len(out), (count * 320 + 146) // 147)
                self.assertLess(abs(len(out) / 48000 - count / 22050), 1 / 48000)
                self.assertEqual(out.shape[1], 2)

    def test_stereo_channels_identical(self):
        out, _ = convert(np.sin(np.arange(22050) * 2 * np.pi * 1000 / 22050) * .5)
        np.testing.assert_array_equal(out[:, 0], out[:, 1])

    def test_tone_frequency_and_image_rejection(self):
        x = .5 * np.sin(np.arange(22050) * 2 * np.pi * 1000 / 22050)
        y, _ = convert(x, gain_db=0)
        v = y[4800:-4800, 0].astype(float)
        spectrum = np.abs(np.fft.rfft(v))
        hz = np.fft.rfftfreq(len(v), 1 / 48000)
        peak = int(np.argmax(spectrum))
        self.assertAlmostEqual(hz[peak], 1000)
        image = int(np.argmin(np.abs(hz - 21050)))
        attenuation = 20 * np.log10(max(spectrum[image], 1e-12) / spectrum[peak])
        self.assertLess(attenuation, -45)

    def test_explicit_file_gain(self):
        t = np.arange(22050) / 22050
        a, _ = convert(.5 * np.sin(2 * np.pi * 1000 * t), gain_db=0)
        b, _ = convert(.5 * np.sin(2 * np.pi * 1000 * t), gain_db=-30)
        ratio = np.max(np.abs(b.astype(np.int32))) / np.max(np.abs(a.astype(np.int32)))
        self.assertAlmostEqual(ratio, 10 ** (-30 / 20), delta=0.0001)

    def test_impulse_preserves_center(self):
        x = np.zeros(22050)
        x[11025] = .5
        out, _ = convert(x, gain_db=0)
        self.assertEqual(int(np.argmax(np.abs(out[:, 0]))), 24000)

    def test_silence_is_not_random_noise(self):
        out, meta = convert(np.zeros(22050))
        self.assertEqual(np.count_nonzero(out), 0)
        self.assertFalse(meta['current_limit_proof'])
        self.assertFalse(meta['playback_attempted'])

    def test_full_scale_has_no_wrap(self):
        x = np.tile([1.0, -1.0], 11025)
        out, meta = convert(x, gain_db=0)
        self.assertLessEqual(int(np.max(np.abs(out.astype(np.int32)))), 32767)
        self.assertLessEqual(meta['boundary_headroom_scale'], 1)

    def test_bad_signal(self):
        for x in [[], [float('nan')], [float('inf')], [[.1, .2]], [1.001], np.zeros(22050 * 30 + 1)]:
            with self.subTest(type=type(x).__name__):
                with self.assertRaises(ValueError):
                    convert(x)

    def test_bad_rate_and_gain(self):
        for args in [{'rate': 48000}, {'gain_db': 1}, {'gain_db': -91}, {'gain_db': float('nan')}]:
            with self.assertRaises(ValueError):
                convert([0.0], **args)

    def test_wav_roundtrip_and_overwrite_refusal(self):
        with tempfile.TemporaryDirectory(prefix='a13-file-pcm-') as folder:
            path = Path(folder) / 'mono.wav'
            data = np.array([0, 123, -123], dtype='<i2')
            write_pcm16(path, data, 22050)
            np.testing.assert_array_equal(read_mono(path) * 32768, data)
            with self.assertRaises(FileExistsError):
                write_pcm16(path, data, 22050)

    def test_stereo_wav_format(self):
        with tempfile.TemporaryDirectory(prefix='a13-file-stereo-') as folder:
            path = Path(folder) / 'stereo.wav'
            out, _ = convert(np.zeros(147))
            write_pcm16(path, out, 48000)
            with wave.open(str(path), 'rb') as wav:
                self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()), (48000, 2, 2, 320))
            with self.assertRaises(ValueError):
                read_mono(path)

    def test_truncated_wav_rejected(self):
        with tempfile.TemporaryDirectory(prefix='a13-file-truncated-') as folder:
            path = Path(folder) / 'truncated.wav'
            write_pcm16(path, np.zeros(100, dtype='<i2'), 22050)
            path.write_bytes(path.read_bytes()[:-2])
            with self.assertRaises(ValueError):
                read_mono(path)

    def test_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory(prefix='a13-file-link-') as folder:
            path = Path(folder) / 'real.wav'
            write_pcm16(path, np.zeros(100, dtype='<i2'), 22050)
            link = Path(folder) / 'link.wav'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                read_mono(link)


class ClockTests(unittest.TestCase):
    def test_codec_16bit_profile(self):
        plan = codec_plan()
        self.assertEqual((plan['PLL_N'], plan['PLL_K_hex']), (8, '0x3126e9'))
        self.assertEqual(plan['nominal_BCLK_hz'], 1536000)
        self.assertEqual(plan['BCLKDIV_field'], 7)
        self.assertEqual(plan['ALRCGPIO'], 1)

    def test_32bit_is_separate_not_silent_default(self):
        plan = codec_plan(32)
        self.assertEqual(plan['nominal_BCLK_hz'], 3072000)
        self.assertEqual(plan['BCLKDIV_field'], 4)

    def test_old_a06_clock_output_would_contend(self):
        for direction, counter in [('OUTPUT', True), ('INPUT_ONLY', True), ('OUTPUT', False)]:
            with self.assertRaises(ValueError):
                require_noncontending_profile(direction, True, counter)

    def test_new_input_only_direction_model(self):
        self.assertIn('NOT_TESTED', require_noncontending_profile('INPUT_ONLY', True, False))

    def test_reject_independent_formatter_cadence(self):
        with self.assertRaises(ValueError):
            require_device_paced_stream(True)
        self.assertIn('CODEC_FRAME', require_device_paced_stream(False))

    def test_oversampling_arithmetic_sweep(self):
        for bits in [16, 32]:
            for hz in [99000000, 99999001, 101000000]:
                for ppm in [-500, 0, 500]:
                    for duty in [Fraction(2, 5), Fraction(1, 2)]:
                        result = oversampling_budget(bits, hz, ppm, duty)
                        self.assertTrue(result['positive_budget'])
                        self.assertFalse(result['measured_or_implemented'])

    def test_slow_oversampling_negative_case(self):
        self.assertFalse(oversampling_budget(32, 10000000, 500, Fraction(2, 5))['positive_budget'])

    def test_no_playback_api_in_runtime(self):
        # Structural guard only, not a sandbox or proof against hostile code.
        for path in (ROOT / 'modules/voice_A/file_tts').glob('*.py'):
            text = path.read_text()
            for token in ['sounddevice', 'pyaudio', 'aplay', '/dev/snd', 'subprocess', 'socket', 'requests']:
                self.assertNotIn(token, text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
