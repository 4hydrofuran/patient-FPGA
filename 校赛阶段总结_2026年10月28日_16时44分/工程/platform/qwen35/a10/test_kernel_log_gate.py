import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch, Mock

from kernel_log_gate import KernelLogGate, KernelLogBlocked, diagnostics, digest
from idle_board_trial import Trial, BOOT

BASE = '<6>[ 1.000000] Linux ready\n'
ERROR = ('<3>[ 4988.494649] OF: ERROR: memory leak, expected refcount 1 instead of 65, '
         'of_node_get()/of_node_put() unbalanced - destroy cset entry: attach overlay node '
         '/axi/interrupt-controller@80020000\n')


class LogGateTests(unittest.TestCase):
    def test_raw_capture_options_compatible_with_actual_board_failure(self):
        trial = Trial.__new__(Trial)
        trial.emit = Mock()
        with patch('idle_board_trial.subprocess.run',
                   return_value=Mock(returncode=0, stderr=b'', stdout=BASE.encode())) as read, \
                patch('idle_board_trial.Path.read_text', return_value=BOOT):
            trial.kernel_checkpoint('preflight', None)
        self.assertEqual(read.call_args.args[0], ['dmesg', '--raw'])
        self.assertNotIn('--color=never', read.call_args.args[0])
        self.assertFalse(read.call_args.kwargs.get('text', False))

    def test_actual_firmware_carriage_returns_remain_in_exact_baseline(self):
        raw = '<4>[ 1.0] firmware warning\r\n  details\r\n'
        trial = Trial.__new__(Trial)
        trial.emit = Mock()
        trial.reviewed_baseline_sha256 = digest(raw)
        with patch('idle_board_trial.subprocess.run',
                   return_value=Mock(returncode=0, stderr=b'', stdout=raw.encode())), \
                patch('idle_board_trial.Path.read_text', return_value=BOOT):
            trial.kernel_checkpoint('preflight', None)
        self.assertEqual(trial.kernel_gate.previous, raw)
        self.assertEqual(trial.emit.call_args.kwargs['raw_log'], raw)

    def test_invalid_raw_encoding_blocks_mutation(self):
        trial = Trial.__new__(Trial)
        trial.emit = Mock()
        with patch('idle_board_trial.subprocess.run',
                   return_value=Mock(returncode=0, stderr=b'', stdout=b'<4> bad\xff\n')), \
                patch('idle_board_trial.Path.read_text', return_value=BOOT), \
                patch('idle_board_trial.subprocess.Popen') as mutate:
            with self.assertRaises(UnicodeDecodeError):
                trial.command(['insmod', 'test.ko'], True)
            mutate.assert_not_called()
            self.assertTrue(trial.kernel_gate.blocked)

    def test_baseline_and_no_change(self):
        gate = KernelLogGate()
        self.assertTrue(gate.observe(BOOT, BASE)['allowed'])
        self.assertTrue(gate.observe(BOOT, BASE)['allowed'])
        self.assertTrue(gate.observe(BOOT, BASE + '<6>[ 2.0] unloaded\n')['allowed'])

    def test_actual_refcount_diagnostic_and_latch(self):
        gate = KernelLogGate()
        gate.observe(BOOT, BASE)
        result = gate.observe(BOOT, BASE + ERROR)
        self.assertFalse(result['allowed'])
        self.assertEqual(result['diagnostics'][0]['text'], ERROR.rstrip())
        self.assertFalse(gate.observe(BOOT, BASE)['allowed'])

    def test_raw_priority_and_text_warning(self):
        for line in ['<4>[ 2.0] opaque message\n', '[ 2.0] OF: overlay: WARNING: memory leak\n',
                     '[ 2.0] IRQ index 32 not found\n', '[ 2.0] Call trace:\n']:
            self.assertTrue(diagnostics(line))

    def test_baseline_requires_exact_review(self):
        for review in [None, 'wrong']:
            self.assertFalse(KernelLogGate().observe(BOOT, BASE + ERROR, review)['allowed'])
        gate = KernelLogGate()
        self.assertTrue(gate.observe(BOOT, BASE + ERROR, digest(BASE + ERROR))['allowed'])
        self.assertTrue(gate.observe(BOOT, BASE + ERROR)['allowed'])
        self.assertFalse(gate.observe(BOOT, BASE + ERROR + ERROR)['allowed'])

    def test_no_deduplication(self):
        self.assertEqual(len(diagnostics(ERROR + ERROR)), 2)

    def test_clear_wrap_reboot_and_missing(self):
        for boot, text in [(BOOT, ''), (BOOT, '<6>[ 4.0] wrapped\n'),
                           ('other-boot', BASE), (BOOT, BASE.rstrip())]:
            gate = KernelLogGate()
            gate.observe(BOOT, BASE)
            self.assertFalse(gate.observe(boot, text)['allowed'])

    def test_runner_blocks_before_mutation(self):
        trial = Trial.__new__(Trial)
        trial.emit = Mock()
        with patch('idle_board_trial.subprocess.run', return_value=Mock(returncode=0, stderr=b'', stdout=(BASE + ERROR).encode())), \
                patch('idle_board_trial.Path.read_text', return_value=BOOT), \
                patch('idle_board_trial.subprocess.Popen') as mutate:
            with self.assertRaises(KernelLogBlocked):
                trial.command(['insmod', 'test.ko'], True)
            mutate.assert_not_called()

    def test_runner_blocks_next_mutation_after_error(self):
        trial = Trial.__new__(Trial)
        trial.emit = Mock()
        child = Mock(returncode=0)
        child.communicate.return_value = ('', '')
        with patch('idle_board_trial.subprocess.run', side_effect=[
                Mock(returncode=0, stderr=b'', stdout=BASE.encode()),
                Mock(returncode=0, stderr=b'', stdout=(BASE + ERROR).encode()),
                Mock(returncode=0, stderr=b'', stdout=(BASE + ERROR).encode())]), \
                patch('idle_board_trial.Path.read_text', return_value=BOOT), \
                patch('idle_board_trial.subprocess.Popen', return_value=child) as mutate:
            with self.assertRaises(KernelLogBlocked):
                trial.command(['dfx-mgr-client', '-remove', '0'], True)
            with self.assertRaises(KernelLogBlocked):
                trial.command(['dfx-mgr-client', '-load', 'k26-starter-kits'], True)
            self.assertEqual(mutate.call_count, 1)

    def test_failed_read_blocks(self):
        for failure in [Mock(returncode=1, stderr='denied', stdout=''),
                        subprocess.TimeoutExpired('dmesg', 3)]:
            trial = Trial.__new__(Trial)
            trial.emit = Mock()
            with patch('idle_board_trial.subprocess.run', side_effect=[failure]), \
                    patch('idle_board_trial.Path.read_text', return_value=BOOT), \
                    patch('idle_board_trial.subprocess.Popen') as mutate:
                with self.assertRaises(Exception):
                    trial.command(['insmod', 'test.ko'], True)
                mutate.assert_not_called()
                self.assertTrue(trial.kernel_gate.blocked)


if __name__ == '__main__':
    unittest.main(verbosity=2)
