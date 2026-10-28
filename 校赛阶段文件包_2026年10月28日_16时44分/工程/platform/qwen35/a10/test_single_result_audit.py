"""PC negative audit of captured BOARD evidence, never replays the test."""
import copy
import unittest
import audit_single_result as audit


class ResultAuditTests(unittest.TestCase):
    def setUp(self):
        self.data = list(copy.deepcopy(audit.load_inputs()))

    def test_actual_capture_passes_only_one_call_postcompute_scope(self):
        result = audit.assess(*self.data)
        self.assertEqual(result['new_compute_submissions'], 1)
        self.assertEqual(result['module_refcount_before_unload'], 0)
        self.assertEqual(result['A10'], 'PENDING_FINAL_REQUIREMENT_AUDIT')
        self.assertIsNone(result['physical_bo_peak_bytes'])

    def test_self_certified_overall_pass_rejected(self):
        self.data[2]['A10'] = 'PASS'
        with self.assertRaisesRegex(RuntimeError, 'self-certify'):
            audit.assess(*self.data)

    def test_wrong_output_cannot_use_recorded_pass_flag(self):
        self.data[2]['worker_result']['actual_output'][0] ^= 1
        with self.assertRaises(RuntimeError):
            audit.assess(*self.data)

    def test_second_submission_is_rejected(self):
        row = next(r for r in self.data[1] if r.get('call') == 'xrtRunStart')
        self.data[1].append(copy.deepcopy(row))
        with self.assertRaisesRegex(RuntimeError, 'one-N32'):
            audit.assess(*self.data)

    def test_pc_fixture_cannot_certify_BOARD(self):
        self.data[2]['worker_result']['PC_FIXTURE_ONLY'] = True
        with self.assertRaisesRegex(RuntimeError, 'PC fixture'):
            audit.assess(*self.data)

    def test_surviving_vma_or_refcount_rejected(self):
        for field, value in (('device_mappings', [{'map': 'deleted render node'}]), ('scan_complete', False)):
            data = copy.deepcopy(self.data)
            row = next(r for r in data[0] if r['event'] == 'RELEASE_PRECHECK_PASSED_NOT_UNLOADED')
            row['scan'][field] = value
            with self.assertRaises(RuntimeError):
                audit.assess(*data)
        row = next(r for r in self.data[0] if r['event'] == 'RELEASE_PRECHECK_PASSED_NOT_UNLOADED')
        row['module_refcount'] = 1
        with self.assertRaises(RuntimeError):
            audit.assess(*self.data)

    def test_actual_exit_and_empty_locks_required(self):
        for index, key, value in ((3, 'manager_proc', {}), (4, 'active_exists', True)):
            data = copy.deepcopy(self.data)
            data[index][key] = value
            with self.assertRaises(RuntimeError):
                audit.assess(*data)
        self.data[0] = [r for r in self.data[0] if r['event'] != 'WORKER_REAPED']
        with self.assertRaisesRegex(RuntimeError, 'waitpid'):
            audit.assess(*self.data)

    def test_late_kernel_fault_is_not_waived(self):
        self.data[6] += b'<3>[ 9999.0] refcount_t: underflow; use-after-free.\n'
        with self.assertRaisesRegex(RuntimeError, 'delayed kernel'):
            audit.assess(*self.data)

    def test_out_of_range_address_cannot_pass(self):
        self.data[2]['worker_result']['addresses'][0] = 0x80000000
        with self.assertRaisesRegex(RuntimeError, 'BO range'):
            audit.assess(*self.data)

    def test_worker_kernel_gate_failure_rejected(self):
        row = next(r for r in self.data[1] if r['event'] == 'WORKER_KERNEL_GATE')
        row['allowed'] = False
        with self.assertRaisesRegex(RuntimeError, 'worker kernel'):
            audit.assess(*self.data)


if __name__ == '__main__':
    unittest.main()
