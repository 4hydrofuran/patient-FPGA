import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import stage_candidate_board as base
import stage_irq2_board as irq2
from original_module_backup import tree_digest


class Irq2StageTests(unittest.TestCase):
    def setUp(self):
        keys = ('BOOT', 'BACKUP_BOOT', 'RELEASE', 'SOURCE', 'FIT_NAME', 'PINNED', 'ZOCL_SHA')
        self.saved = {k: getattr(base, k) for k in keys}
        irq2.configure()

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(base, k, v)

    def test_explicit_distinct_paths_no_boot(self):
        p = irq2.plan()
        self.assertEqual(p['kernel_release'], '6.8.12-a10irq2')
        self.assertEqual(p['candidate_fit'], '/boot/firmware/a10-candidate-irq2-20261021.fit')
        self.assertNotEqual(p['current_boot'], p['backup_source_boot'])
        self.assertTrue(p['current_original_tree_rehash_required'])
        for key in ('QSPI_write', 'default_boot_change', 'module_load', 'compute', 'boot_authorized'):
            self.assertFalse(p[key])

    def proof(self):
        rows = [dict(path='modules.dep', kind='file', bytes=0, mode=420, uid=0, gid=0,
                     sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')]
        return dict(schema='A10_ORIGINAL_MODULE_BACKUP_PROOF_V1', status='VERIFIED_PC_BACKUP',
                    release='6.8.0-1015-xilinx', identity=dict(boot_id=irq2.BACKUP_BOOT,
                    machine_sha256=base.MACHINE_SHA), rows=rows, tree_sha256=tree_digest(rows))

    def test_old_proof_requires_current_tree_readback(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'proof.json'; p.write_text(json.dumps(self.proof()))
            with patch.object(base, 'current_tree_matches') as compare:
                base.check_backup_proof(p, base.digest(p), Path(t) / 'old')
                compare.assert_called_once()

    def test_changed_current_tree_stops_before_staging(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'proof.json'; p.write_text(json.dumps(self.proof()))
            with patch.object(base, 'current_tree_matches', side_effect=ValueError('changed')):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    base.check_backup_proof(p, base.digest(p), Path(t) / 'old')

    def test_proof_identity_not_relabelled_as_current_boot(self):
        with tempfile.TemporaryDirectory() as t:
            proof = self.proof(); proof['identity']['boot_id'] = irq2.BOOT
            p = Path(t) / 'proof.json'; p.write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, 'pinned source'):
                base.check_backup_proof(p, base.digest(p), Path(t) / 'old')


if __name__ == '__main__':
    unittest.main()
