"""PC models/source guards only; none of these tests run a board or RTL."""
import importlib.util
from pathlib import Path
import unittest

from calculations import mixed_values, pll_factors, pullup_budget, relative_drift_samples, xiic_registers
from prepare_locked import derive_card, derive_formatter

ROOT = Path(__file__).resolve().parents[4]


class OfflineTests(unittest.TestCase):
    def test_fs_allowed_change_single_bit(self):
        self.assertEqual(mixed_values(384, 256, 16), {384, 256})

    def test_cold_fs_sync_not_atomic(self):
        # Source default 0x180 can first reach a zero-initialized bus as 0x80.
        self.assertEqual(mixed_values(0, 384, 16), {0, 128, 256, 384})

    def test_arbitrary_multiplier_is_unsafe(self):
        self.assertNotEqual(mixed_values(255, 256, 16), {255, 256})

    def test_chmux_fixed_stereo_transition(self):
        self.assertEqual(mixed_values(0, 1, 3), {0, 1})

    def test_chmux_change_can_tear(self):
        self.assertEqual(mixed_values(1, 2, 3), {0, 1, 2, 3})

    def test_model_input_width(self):
        with self.assertRaises(ValueError):
            mixed_values(0, 8, 3)

    def test_2k_100pf_passes_rise_model(self):
        self.assertAlmostEqual(pullup_budget(2000, 100)['rise_30_70_ns'], 169.46)

    def test_2k_200pf_fails_codec_even_at_100k(self):
        self.assertGreater(pullup_budget(2000, 200)['rise_30_70_ns'], 300)

    def test_max_capacitance(self):
        self.assertAlmostEqual(pullup_budget(2000, 0)['C_max_at_300ns_pf'], 177.032928, places=5)

    def test_pullups_are_not_the_whole_current(self):
        self.assertAlmostEqual(2 * pullup_budget(2000, 0)['I_one_low_mA_upper_ideal'], 3.3)

    def test_input_validation(self):
        for args in [(0, 100), (2000, -1)]:
            with self.assertRaises(ValueError):
                pullup_budget(*args)

    def test_iic_rounded_timer_values(self):
        self.assertEqual(xiic_registers(99999001), {
            'THIGH': 492, 'TLOW': 492, 'THDDAT': 1,
            'TSUSTA': 569, 'TSUSTO': 499, 'THDSTA': 429, 'TSUDAT': 54, 'TBUF': 499})

    def test_iic_alternate_mode_not_approved(self):
        with self.assertRaises(ValueError):
            xiic_registers(99999001, 400000)

    def test_nominal_audio_clock_ratios(self):
        self.assertEqual(12288000 // 4, 3072000)
        self.assertEqual(12288000 // 256, 48000)
        self.assertEqual(3072000 // 48000, 64)

    def test_pll_nominal_factors(self):
        result = pll_factors(24000000, 24576000)
        self.assertEqual((result['pre_div'], result['n'], result['k']), (1, 8, 0x3126e9))
        self.assertLess(abs(float(result['output_hz_fraction']) / 2 - 12288000), 1)

    def test_pll_invalid(self):
        with self.assertRaises(ValueError):
            pll_factors(24000000, 1000000)

    def test_equal_nominal_is_not_common_clock(self):
        # Illustrative 100ppm difference only, not a measured oscillator error.
        self.assertEqual(relative_drift_samples(48000, 100, 1), 4.8)
        self.assertEqual(relative_drift_samples(48000, 100, 10), 48)

    def test_card_has_no_latent_clock_programming(self):
        text = derive_card((ROOT / 'platform/qwen35/a13/audio_pl/a13_wm8960_card.c').read_text())
        self.assertNotIn('snd_soc_dai_set_pll(', text)
        self.assertNotIn('snd_soc_dai_set_sysclk(', text)
        block = text.split('static int a13_params(', 1)[1].split('static const struct snd_soc_ops', 1)[0]
        self.assertIn('return -EPERM;', block)
        self.assertNotIn('module_param', text)

    def test_formatter_rejects_params(self):
        # Use the actual retained kernel source, rather than a synthetic driver.
        old = ROOT / 'platform/qwen35/a13/audio_pl/prepare_modules.py'
        spec = importlib.util.spec_from_file_location('a13_old_test', old)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = ROOT / ('evidence/a13_A/20261024-audio-pl-v1/delivery/builds/'
            '01792835847348851974-A-a13-audio-modules-v3-8cebf031/sources/xlnx_formatter_original.c')
        text = derive_formatter(original.read_text(), module.derive)
        self.assertIn('.hw_params\t= a13_locked_params,', text)
        self.assertIn('.open\t\t= a13_locked_open,', text)
        self.assertIn('.trigger\t= a13_locked_trigger,', text)
        block = text.split('static int a13_locked_params(', 1)[1].split('static const struct snd_soc_component_driver', 1)[0]
        self.assertIn('return -EPERM;', block)
        self.assertNotIn('iowrite', block)


if __name__ == '__main__':
    unittest.main(verbosity=2)
