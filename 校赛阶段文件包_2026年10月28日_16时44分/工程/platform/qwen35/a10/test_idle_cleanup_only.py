import unittest
from idle_cleanup_only import cleanup_lease_gate, cleanup_command_gate, restored_gate, MACHINE, BOOT
from idle_board_trial import accelerator_fd, check_removed


class CleanupTests(unittest.TestCase):
    def test_legacy_drm_node_is_also_a_holder(self):
        for p in ['/dev/dri/card1', '/dev/dri/card1 (deleted)', '/dev/dri/renderD128', '/dev/uio0']:
            self.assertTrue(accelerator_fd(p, ['/dev/dri/card1']))
        self.assertFalse(accelerator_fd('/dev/dri/card0', ['/dev/dri/card1']))
        with self.assertRaises(RuntimeError):
            check_removed(dict(overlays={}, zocl_bound=[], render_nodes=[], device_holders=[],
                               module_refcount=False), True)

    def test_only_scoped_lease(self):
        good = dict(owner='A', scope='A10_IDLE_PL_ONCE', identity=MACHINE + ':' + BOOT,
                    compute_authorized=False, pid=123)
        cleanup_lease_gate(good)
        for k, v in [('owner', 'B'), ('scope', 'COMPUTE'), ('identity', 'other'),
                     ('compute_authorized', True), ('pid', False), ('pid', 1)]:
            with self.assertRaises(RuntimeError):
                cleanup_lease_gate({**good, k: v})

    def test_only_normal_cleanup_commands(self):
        for argv in [['rmmod', 'zocl'], ['dfx-mgr-client', '-remove', '0'],
                     ['dfx-mgr-client', '-load', 'k26-starter-kits']]:
            cleanup_command_gate(argv, True)
        for argv in [['dfx-mgr-client', '-load', 'a10-vadd-20261019'], ['rmmod', '-f', 'zocl'],
                     ['reboot'], ['dfx-mgr-client', '-remove', '-1'], ['insmod', 'zocl.ko']]:
            with self.assertRaises(RuntimeError):
                cleanup_command_gate(argv, True)
        with self.assertRaises(RuntimeError):
            cleanup_command_gate(['rmmod', 'zocl'], False)
        cleanup_command_gate(['dfx-mgr-client', '-listPackage'], False)

    def test_restore_requires_all_readbacks(self):
        initial = dict(overlays={'k26-starter-kits_image_1': 'applied'}, vart_sha256=None)
        final = dict(**initial, module_refcount=None, zocl_bound=[], render_nodes=[],
                     device_holders=[], accelerator_card_nodes=[], fpga_state='operating')
        restored_gate(final, initial)
        for k, v in [('module_refcount', 0), ('zocl_bound', ['residual']), ('render_nodes', ['residual']),
                     ('device_holders', [12]), ('accelerator_card_nodes', ['card1']),
                     ('overlays', {}), ('fpga_state', 'unknown'), ('vart_sha256', 'changed')]:
            with self.assertRaises(RuntimeError):
                restored_gate({**final, k: v}, initial)


if __name__ == '__main__':
    unittest.main(verbosity=2)
