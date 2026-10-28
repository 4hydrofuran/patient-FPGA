"""PS display is not a PL consumer; unknown/deleted accelerator users still block."""
import copy
import os
from pathlib import Path
import stat
import unittest
from unittest.mock import patch

import accelerator_release_gate_v2 as release
from test_xrt_worker_boundary import clear_snapshot


class PSDisplayTests(unittest.TestCase):
    def setUp(self):
        self.proof = dict(path=release.PS_DISPLAY,
                          driver='/sys/bus/platform/drivers/zynqmp-display',
                          sys_device='/sys/devices/platform/axi/fd4a0000.display', dev='226:0',
                          identity=dict(mode=stat.S_IFCHR | 0o660, device=5,
                                        rdev=226 * 256, inode=662, uid=0))

    def row(self, **changes):
        parts = dict(path='/dev/dri/card0', inode=662, device='00:05')
        parts.update(changes)
        return '1000-2000 rw-s 00000000 {device} {inode} {path}'.format(**parts)

    def test_verified_display_fd_only_exact_identity(self):
        identity = self.proof['identity']
        self.assertTrue(release.is_ps_display_fd('/dev/dri/card0', identity, self.proof))
        for path in ('/dev/dri/card1', '/dev/dri/renderD128', '/dev/dri/card0 (deleted)', '/dev/zocl'):
            self.assertFalse(release.is_ps_display_fd(path, identity, self.proof))
        for key in identity:
            wrong = dict(identity)
            wrong[key] += 1
            self.assertFalse(release.is_ps_display_fd('/dev/dri/card0', wrong, self.proof))

    @unittest.skipUnless(hasattr(os, 'major'), 'Linux device encoding')
    def test_display_map_inode_and_filesystem_device_must_match(self):
        self.assertTrue(release.is_ps_display_map(self.row(), self.proof))
        for change in (dict(inode=663), dict(device='00:06'), dict(path='/dev/dri/card0 (deleted)'),
                       dict(path='/dev/dri/renderD128'), dict(path='/dev/dri/card1')):
            self.assertFalse(release.is_ps_display_map(self.row(**change), self.proof))
        self.assertFalse(release.is_ps_display_map(self.row(), None))

    def test_binding_read_failure_cannot_produce_clean_scan(self):
        with patch.object(release, 'ps_display_identity', side_effect=OSError('unknown binding')):
            # A fake boot reader reaches binding verification without hardware.
            with patch.object(Path, 'read_text', return_value='test-boot'):
                result = release.collect(allow_ps_display=True)
        self.assertFalse(result['scan_complete'])
        with self.assertRaises(RuntimeError):
            release.require_no_users(result, True, boot_id='test-boot')

    @unittest.skipUnless(hasattr(os, 'major'), 'Linux device encoding')
    def test_ps_display_does_not_hide_deleted_xrt_vma_or_refcount(self):
        scan = clear_snapshot()
        scan.update(ps_display_before=self.proof, ps_display_after=self.proof,
                    ps_display_holders=[dict(pid=1, fd='20', target=release.PS_DISPLAY,
                                             identity=self.proof['identity'])],
                    ps_display_mappings=[dict(pid=42, map=self.row())])
        release.require_release(scan, 0, True, boot_id='test-boot')
        with self.assertRaisesRegex(RuntimeError, 'MODULE_REFERENCE'):
            release.require_release(scan, 1, True, boot_id='test-boot')
        dirty = copy.deepcopy(scan)
        dirty['device_mappings'] = [dict(pid=100, map=self.row(path='/dev/dri/renderD128 (deleted)'))]
        with self.assertRaisesRegex(RuntimeError, 'VMA_STILL_MAPPED'):
            release.require_release(dirty, 0, True, boot_id='test-boot')
        dirty = copy.deepcopy(scan)
        dirty['ps_display_after']['identity']['inode'] += 1
        # deepcopy preserves the shared before/after reference; replace after.
        dirty['ps_display_before'] = self.proof
        with self.assertRaisesRegex(RuntimeError, 'PROOF_MISSING_OR_CHANGED'):
            release.require_release(dirty, 0, True, boot_id='test-boot')


if __name__ == '__main__':
    unittest.main()
