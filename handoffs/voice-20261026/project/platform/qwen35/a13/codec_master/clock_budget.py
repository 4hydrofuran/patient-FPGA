"""已声明假设下的离散采样与引脚预算；不是亚稳态、MTBF或电气实测。"""
from fractions import Fraction
from math import ceil
import unittest


def reconvergence_margin(delay_stages, clock_hz, phase_ns, relative_pad_delay_ns,
                         extra_lr_capture_cycles=1):
    """按同一系统时钟的NBA先读旧值规则，核对LR在发送译码前稳定。"""
    tick = Fraction(10**9, clock_hz)
    bclk_first = ceil(Fraction(phase_ns) / tick)
    lr_first = ceil((Fraction(phase_ns) + relative_pad_delay_ns) / tick)
    lr_first += extra_lr_capture_cycles
    # 三FF的末级在first+2，channel Q在first+3；命令在BCLK first+D+4。
    # 必须严格早于译码边沿，不能依赖同边沿新Q被读到。
    channel_time = (lr_first + 3) * tick
    command_time = (bclk_first + delay_stages + 4) * tick
    return command_time - channel_time


def tx_budget(clock_hz=99000000, codec_ppm=500, delay_stages=4):
    tick = Fraction(10**9, clock_hz)
    bclk = Fraction(48000 * 32) * (1 + Fraction(codec_ppm, 1000000))
    half = Fraction(10**9, 1) / bclk * Fraction(2, 5)
    # 输入至第一级D最多10ns；D+6拍含相位量化，再加一次额外捕获假设。
    # 寄存器至DAC pad预算20ns、器件setup10ns；线缆及额外抖动必须另测。
    digital = 10 + (delay_stages + 7) * tick
    remainder = half - digital - 20 - 10
    return {'minimum_half_ns_assumed': float(half),
            'input_and_pipeline_ns_bound_assumed': float(digital),
            'DAC_route_budget_ns': 20, 'codec_setup_ns': 10,
            'remaining_wire_and_extra_jitter_ns': float(remainder),
            'positive_under_assumptions': remainder > 0,
            'metastability_extra_cycles_is_assumption_not_guarantee': True,
            'BOARD': 'NOT_TESTED', 'MTBF_s': None}


class ClockBudgetTests(unittest.TestCase):
    def test_four_wait_stages_cover_declared_skew(self):
        for hz in [99000000, 99999001, 101000000]:
            for phase in range(101):
                for delay in [0, 10, 20]:
                    self.assertGreater(reconvergence_margin(4, hz, Fraction(phase, 10), delay), 0)

    def test_two_wait_stages_have_a_counterexample(self):
        self.assertLessEqual(reconvergence_margin(2, 101000000, Fraction(1, 10), 20), 0)

    def test_tx_budget_is_positive_not_measured(self):
        value = tx_budget()
        self.assertGreater(value['remaining_wire_and_extra_jitter_ns'], 100)
        self.assertIsNone(value['MTBF_s'])

    def test_slow_system_clock_is_not_accepted(self):
        self.assertFalse(tx_budget(clock_hz=10000000)['positive_under_assumptions'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
