import copy
import unittest

import audit_isolated_idle_result as audit


class CaptureAuditTests(unittest.TestCase):
    def setUp(self):
        self.data = list(copy.deepcopy(audit.load_inputs()))

    def test_actual_capture_only_passes_idle_not_A10(self):
        result = audit.assess(*self.data)
        self.assertEqual(result['status'], 'PASS_BOARD_IDLE_WITH_KNOWN_LIMITATIONS')
        self.assertTrue(result['A10'].startswith('NOT_PASSED'))
        self.assertEqual(result['new_compute_submissions'], 0)

    def test_fake_overall_acceptance_refused(self):
        self.data[2]['A10'] = 'PASS'
        with self.assertRaisesRegex(RuntimeError, 'idle cannot certify'):
            audit.assess(*self.data)

    def test_live_manager_or_lease_refused(self):
        for index, key, value in ((3, 'manager_proc', {}), (4, 'active_exists', True)):
            data = copy.deepcopy(self.data)
            data[index][key] = value
            with self.assertRaises(RuntimeError):
                audit.assess(*data)

    def test_missing_normal_exit_refused(self):
        self.data[0] = [r for r in self.data[0] if r['event'] != 'WORKER_REAPED']
        with self.assertRaisesRegex(RuntimeError, 'normal waitpid'):
            audit.assess(*self.data)

    def test_surviving_mapping_refused(self):
        row = next(r for r in self.data[0] if r['event'] == 'RELEASE_PRECHECK_PASSED_NOT_UNLOADED')
        row['scan']['device_mappings'] = [{'path': '/dev/dri/renderD128 (deleted)'}]
        with self.assertRaisesRegex(RuntimeError, 'release incomplete'):
            audit.assess(*self.data)

    def test_late_new_kernel_fault_refused(self):
        self.data[6] += b'<3>[ 8000.000000] refcount_t: underflow; use-after-free.\n'
        with self.assertRaisesRegex(RuntimeError, 'delayed kernel'):
            audit.assess(*self.data)


if __name__ == '__main__':
    unittest.main()
