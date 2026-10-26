"""Architecture arithmetic/safety model; not a serializer or RTL simulation."""
from fractions import Fraction
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def codec_plan(slot_bits=16):
    if slot_bits not in [16, 32]:
        raise ValueError('reviewed slots are 16 or 32 bits')
    spec = importlib.util.spec_from_file_location('a13_reviewed_clock_math',
        ROOT / 'platform/qwen35/a13/audio_signoff/calculations.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pll = module.pll_factors(24000000, 24576000)
    sysclk = pll['output_hz_fraction'] / 2
    fs = sysclk / 256
    bclk_divisor = 8 if slot_bits == 16 else 4
    bclk = sysclk / bclk_divisor
    assert bclk / fs == 2 * slot_bits
    return {'oscillator_hz': 24000000, 'PLL_predivide_by_2': pll['pre_div'],
            'PLL_N': pll['n'], 'PLL_K_hex': hex(pll['k']),
            'SYSCLKDIV_divisor': 2, 'ADCDIV_DACDIV_divisor': 1,
            'SYSCLK_hz_exact_model': str(sysclk), 'Fs_hz_exact_model': str(fs),
            'BCLK_hz_exact_model': str(bclk), 'nominal_Fs_hz': 48000,
            'nominal_BCLK_hz': 48000 * 2 * slot_bits,
            'slot_bits': slot_bits, 'word_bits': 16, 'channels': 2,
            'codec_clock_role': 'MASTER', 'BCLKDIV_divisor': bclk_divisor,
            'BCLKDIV_field': 7 if slot_bits == 16 else 4,
            'ALRCGPIO': 1, 'pin14': 'UNCHANGED_UNCONNECTED',
            'format': 'I2S_ONE_BIT_DELAY', 'analog_enable': False,
            'implementation': 'ARITHMETIC_ONLY_NOT_REGISTER_WRITES'}


def oversampling_budget(slot_bits, fast_hz, ppm, minimum_half_fraction, detect_cycles=4):
    if fast_hz <= 0 or slot_bits not in [16, 32] or abs(ppm) > 10000:
        raise ValueError('invalid clock-model input')
    if not 0 < minimum_half_fraction <= Fraction(1, 2) or detect_cycles < 2:
        raise ValueError('invalid edge model')
    fs = Fraction(48000) * (1 + Fraction(ppm, 1000000))
    bclk = fs * 2 * slot_bits
    window_ns = Fraction(1000000000) / bclk * minimum_half_fraction
    latency_ns = Fraction(1000000000) * detect_cycles / fast_hz
    # 10ns DAC setup taken from codec timing table. Remaining budget is NOT a
    # measured pad/wire delay. A future implementation must prove it in STA/IO.
    remainder_ns = window_ns - latency_ns - 10
    return {'fast_hz': fast_hz, 'codec_ppm_assumed': ppm,
            'minimum_half_cycle_ns': float(window_ns),
            'digital_edge_detection_bound_ns_assumed': float(latency_ns),
            'remaining_TX_pad_wire_jitter_budget_ns': float(remainder_ns),
            'positive_budget': remainder_ns > 0,
            'measured_or_implemented': False}


def require_noncontending_profile(pl_clock_direction, codec_master, old_counter_connected):
    if codec_master and (pl_clock_direction != 'INPUT_ONLY' or old_counter_connected):
        raise ValueError('potential BCLK/LRCLK double drive')
    if codec_master and not old_counter_connected:
        return 'DIRECTION_MODEL_ONLY_BOARD_SEQUENCE_NOT_TESTED'
    raise ValueError('this review requires codec-master common sampling reference')


def require_device_paced_stream(independent_Fs_generator):
    if independent_Fs_generator:
        raise ValueError('independent nominal sample clock is not accepted as common reference')
    return 'TRANSPORT_MUST_FOLLOW_CODEC_FRAME_EVENTS_WITH_BACKPRESSURE'
