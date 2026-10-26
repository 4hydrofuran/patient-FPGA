import copy
import hashlib
import json
from pathlib import Path
import unittest
from candidate_idle_cleanup_20261021 import commands_allowed, restored, validate_stop, RAW_SHA, STOP_SHA


class CleanupTests(unittest.TestCase):
    def test_real_captured_stop_matches_pinned_bytes_and_review(self):
        capture = (Path(__file__).resolve().parents[3] /
                   'evidence/board_platform/A10_20261018_intake/'
                   'idle_window_trial_v3_raw_20261021_01.jsonl').read_bytes()
        self.assertEqual(hashlib.sha256(capture).hexdigest(), STOP_SHA)
        self.assertEqual(len(RAW_SHA), 64)
        rows = [json.loads(line) for line in capture.splitlines()]
        self.assertEqual(validate_stop(rows)['phase'], 'initial')
        last = [r for r in rows if r['event'] == 'KERNEL_LOG_GATE'][-1]
        self.assertEqual(hashlib.sha256(last['raw_log'].encode()).hexdigest(), RAW_SHA)

    def test_only_two_normal_restoration_commands(self):
        for command in [['rmmod', 'zocl'], ['dfx-mgr-client', '-load', 'k26-starter-kits']]:
            commands_allowed(command, True)
        for command in [['rmmod', '-f', 'zocl'], ['insmod', 'zocl.ko'], ['reboot'],
                        ['dfx-mgr-client', '-remove', '0'],
                        ['dfx-mgr-client', '-load', 'a10-vadd-20261021-candidate']]:
            with self.assertRaises(RuntimeError):
                commands_allowed(command, True)

    def test_state_mutation_cannot_pose_as_readonly(self):
        with self.assertRaises(RuntimeError):
            commands_allowed(['rmmod', 'zocl'], False)
        commands_allowed(['dfx-mgr-client', '-listPackage'], False)

    def test_exact_stop_only(self):
        rows = [
            dict(event='READBACK', phase='initial'),
            dict(event='COMMAND_BEGIN', state_changing=True,
                 argv=['dfx-mgr-client', '-remove', '0']),
            dict(event='COMMAND_BEGIN', state_changing=True,
                 argv=['insmod', '/usr/lib/modules/6.8.12-a10irq1/extra/zocl.ko']),
            dict(event='KERNEL_LOG_GATE', reason='NEW_KERNEL_DIAGNOSTIC',
                 current_sha256=RAW_SHA,
                 new_text='<4>[ 1224.225715] zocl: loading out-of-tree module taints kernel.\n'),
            dict(event='STOP_NO_AUTOMATIC_RECOVERY')]
        self.assertEqual(validate_stop(rows), rows[0])
        for key, value in [('reason', 'NO_NEW_DIAGNOSTIC'), ('current_sha256', 'other'),
                           ('new_text', 'IRQ index 32 not found\n')]:
            changed = copy.deepcopy(rows)
            changed[-2][key] = value
            with self.assertRaises(RuntimeError):
                validate_stop(changed)
        changed = copy.deepcopy(rows)
        changed[2]['argv'] = ['dfx-mgr-client', '-load', 'test']
        with self.assertRaises(RuntimeError):
            validate_stop(changed)

    def test_restored_requires_all_independent_state(self):
        initial = dict(overlays={'k26-starter-kits_image_1': 'applied'}, vart_sha256=None)
        final = dict(**initial, module_refcount=None, zocl_bound=[], render_nodes=[],
                     device_holders=[], accelerator_card_nodes=[], fpga_state='operating')
        restored(final, initial)
        for key, value in [('overlays', {}), ('module_refcount', 0),
                           ('device_holders', [1]), ('accelerator_card_nodes', ['card1']),
                           ('render_nodes', ['renderD128']), ('zocl_bound', ['zocl']),
                           ('vart_sha256', 'changed'), ('fpga_state', 'unknown')]:
            with self.assertRaises(RuntimeError):
                restored({**final, key: value}, initial)


if __name__ == '__main__':
    unittest.main(verbosity=2)
