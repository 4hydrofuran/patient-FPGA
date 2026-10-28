import tempfile
import unittest
from pathlib import Path
from prepare_idle_trial import make_plan, prepare, confirm_removed

ROOT = Path(__file__).resolve().parents[3]


class IdleTrialTests(unittest.TestCase):
    def test_fixed_inputs_and_no_authorization(self):
        p = make_plan(ROOT)
        self.assertFalse(p['authorized'])
        self.assertFalse(p['compute_authorized'])
        self.assertFalse(p['execution_performed'])
        self.assertEqual(p['real_comparisons'], 0)
        self.assertEqual(len(p['artifacts']), 2)
        self.assertEqual(p['restore_artifact_hashes']['k26_starter_kits.dtbo'], '1e998ffd5d33a05da3746df3603e65603e1628006bc878209a836cc9bd3c4ae1')

    def test_package_has_no_executable_or_xclbin(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'candidate'
            prepare(ROOT, out)
            self.assertEqual({p.name for p in out.iterdir()}, {'a1-vadd.bit.bin', 'a1-vadd.dtbo', 'shell.json', 'plan.pending.json'})
            with self.assertRaises(FileExistsError):
                prepare(ROOT, out)

    def test_exit_zero_insufficient(self):
        self.assertFalse(confirm_removed({'query_exit': 0, 'remove_exit': 0}))

    def test_independent_readback_required(self):
        good = dict(query_exit=0, test_overlays=[], zocl_bound_devices=[], accelerator_render_nodes=[],
                    accelerator_open_holders=[], module_refcount=0)
        self.assertTrue(confirm_removed(good))
        for key in ['test_overlays', 'zocl_bound_devices', 'accelerator_render_nodes', 'accelerator_open_holders']:
            self.assertFalse(confirm_removed({**good, key: ['still-present']}))
        for count in [None, 1, False, '0']:
            self.assertFalse(confirm_removed({**good, 'module_refcount': count}))
        self.assertFalse(confirm_removed({**good, 'query_exit': 1}))


if __name__ == '__main__':
    unittest.main(verbosity=2)
