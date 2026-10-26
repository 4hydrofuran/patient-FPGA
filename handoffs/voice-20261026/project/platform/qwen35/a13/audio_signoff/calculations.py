"""Offline arithmetic models, not RTL simulation or a hardware enable policy."""
from fractions import Fraction
from itertools import product


def mixed_values(before, after, width):
    """All independent per-bit old/new samples; does not model analog metastability."""
    if not 0 <= before < 2 ** width or not 0 <= after < 2 ** width:
        raise ValueError('value outside bus width')
    changed = [bit for bit in range(width) if (before ^ after) & (1 << bit)]
    return {before ^ sum((1 << bit) * take for bit, take in zip(changed, choice))
            for choice in product([0, 1], repeat=len(changed))}


def pullup_budget(resistance_ohm, capacitance_pf, supply_v=3.3):
    if resistance_ohm <= 0 or capacitance_pf < 0 or supply_v <= 0:
        raise ValueError('invalid electrical model input')
    return {'rise_30_70_ns': 0.8473 * resistance_ohm * capacitance_pf / 1000,
            'C_max_at_300ns_pf': 300000 / (0.8473 * resistance_ohm),
            'I_one_low_mA_upper_ideal': supply_v / resistance_ohm * 1000}


def xiic_registers(input_hz, scl_hz=100000):
    """Exact integer arithmetic of the matching irq2 Linux xiic_setclk at 100k."""
    if input_hz <= 0 or scl_hz != 100000:
        raise ValueError('this reviewed model is only Standard-mode 100k')
    ceil = lambda num, den: (num + den - 1) // den
    mhz = ceil(input_hz, 1000000)
    high = ceil(input_hz, 2 * scl_hz) - 7 - 1
    timers = dict(zip(['TSUSTA', 'TSUSTO', 'THDSTA', 'TSUDAT', 'TBUF'],
                      [5700, 5000, 4300, 550, 5000]))
    result = {'THIGH': high, 'TLOW': high, 'THDDAT': 1}
    result.update({key: value * mhz // 1000 - 1 for key, value in timers.items()})
    if any(value < 0 or value > 0xffffffff for value in result.values()):
        raise ValueError('timer out of range')
    return result


def pll_factors(source, output):
    """Integer rounding in irq2 wm8960 pll_factors, not a lock/sync proof."""
    if source <= 0 or output <= 0:
        raise ValueError('positive frequencies required')
    target = output * 4
    n = target // source
    pre = 0
    if n < 6:
        source >>= 1
        pre = 1
        n = target // source
    if not 6 <= n <= 12:
        raise ValueError('unsupported PLL N')
    remainder = target % source
    ten_k = (1 << 24) * 10 * remainder // source
    k = (ten_k + (5 if ten_k % 10 >= 5 else 0)) // 10
    return {'pre_div': pre, 'n': n, 'k': k,
            'output_hz_fraction': Fraction(source) * (n + Fraction(k, 1 << 24)) / 4}


def relative_drift_samples(rate_hz, ppm_difference, seconds):
    if rate_hz <= 0 or seconds < 0:
        raise ValueError('invalid drift input')
    return rate_hz * ppm_difference / 1e6 * seconds
