import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from prepare_driver import prepare, once, function, PINS

BUNDLE = Path(__file__).resolve().parents[3] / 'build/a10-driver-irq-repair-20261019-v1'


class DriverCandidateTests(unittest.TestCase):
    def test_exact_scope_hashes(self):
        manifest = json.loads((BUNDLE / 'manifest.json').read_text())
        self.assertEqual(set(manifest['files']), set(PINS))
        for name, row in manifest['files'].items():
            for kind in ['original', 'candidate']:
                self.assertEqual(hashlib.sha256((BUNDLE/kind/name).read_bytes()).hexdigest(), row[kind+'_sha256'])

    def test_early_irq_and_teardown_order(self):
        text = (BUNDLE/'candidate/common/cu.c').read_text()
        probe = function(text, 'cu_probe')['text']
        remove = function(text, 'cu_remove')['text']
        self.assertLess(probe.index('xrt_cu_hls_init'), probe.index('zocl_ert_intc_add'))
        self.assertLess(probe.index('goto err2'), probe.index('zocl_ert_intc_add'))
        self.assertLess(remove.index('sysfs_remove_group'), remove.index('zocl_ert_intc_remove'))
        self.assertLess(remove.index('zocl_ert_intc_remove'), remove.index('xrt_cu_hls_fini'))
        self.assertNotIn('write_lock(', remove)

    def test_sleepable_and_spinlock_separation(self):
        text = (BUNDLE/'candidate/zert/zocl_xgq_intc.c').read_text()
        self.assertIn('mutex_init(&zintc->zei_lock)', text)
        self.assertNotIn('spin_lock_irqsave(&zintc->zei_lock', text)
        release = function(text, 'a10_irq_release_locked')['text']
        self.assertLess(release.index('free_irq('), release.index('spin_lock_irqsave('))
        add = function(text, 'zocl_irq_intc_add')['text']
        self.assertIn('IRQF_NO_AUTOEN', add)
        self.assertLess(add.index('spin_unlock_irqrestore'), add.index('enable_irq('))

    def test_ambiguous_anchor_rejected(self):
        for value in ['', 'xxx']:
            with self.assertRaises(ValueError):
                once(value, 'x', 'y')

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):
                prepare(BUNDLE/'original', Path(temp))

    def test_wrong_source_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in PINS:
                p = root/'source'/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                prepare(root/'source', root/'out')
            self.assertFalse((root/'out').exists())


if __name__ == '__main__':
    unittest.main()
