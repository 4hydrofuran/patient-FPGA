import unittest
from audit_idle_window_20261021 import derive, mutation_summary


class EvidenceAuditTests(unittest.TestCase):
    def test_actual_hashed_captures_cannot_be_called_A10_pass(self):
        result = derive()
        self.assertEqual(result['status'], 'DEFAULT_RESTORED_DIAGNOSTICS_OPEN_A10_NOT_PASSED')
        self.assertEqual(result['test_bitstream_loads'], 0)
        self.assertEqual(result['compute_runs'], 0)
        self.assertEqual(result['compute_BO_allocations'], 0)
        self.assertEqual(result['baseline_CR_translation_reproduced'], 41)
        self.assertTrue(result['default_overlay_restored'])
        self.assertFalse(result['zocl_loaded'])

    def test_unfinished_or_duplicate_completion_rejected(self):
        begin = dict(event='COMMAND_BEGIN', argv=['rmmod', 'zocl'],
                     state_changing=True, monotonic_s=1)
        end = dict(event='COMMAND_END', argv=['rmmod', 'zocl'],
                   exit_code=0, monotonic_s=2)
        for capture in [[begin], [begin, end, end]]:
            with self.assertRaises(RuntimeError):
                mutation_summary(capture)

    def test_readonly_not_counted_and_failure_not_hidden(self):
        events = [
            dict(event='COMMAND_BEGIN', argv=['dmesg'], state_changing=False, monotonic_s=0),
            dict(event='COMMAND_BEGIN', argv=['rmmod', 'zocl'], state_changing=True, monotonic_s=1),
            dict(event='COMMAND_END', argv=['rmmod', 'zocl'], exit_code=1, monotonic_s=1.5)]
        result = mutation_summary(events)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['exit_code'], 1)
        self.assertEqual(result[0]['elapsed_s'], .5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
