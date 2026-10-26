import unittest
from idle_board_trial import active_handle, check_removed, check_loaded, PACKAGE


class Gates(unittest.TestCase):
    def test_observed_handle(self):
        self.assertEqual(active_handle('k26-starter-kits XRT_FLAT 0->7,', 'k26-starter-kits'), '7')
        for row in ['', 'k26-starter-kits XRT_FLAT -1', 'k26-starter-kits XRT_FLAT 0->0, 1->1,']:
            with self.assertRaises(RuntimeError):
                active_handle(row, 'k26-starter-kits')

    def test_remove_independent_of_exit(self):
        good = dict(overlays={}, zocl_bound=[], render_nodes=[], device_holders=[], module_refcount=0)
        check_removed(good, True)
        check_removed({**good, 'module_refcount': None}, False)
        for key in ('overlays', 'zocl_bound', 'render_nodes', 'device_holders', 'module_refcount'):
            with self.assertRaises(RuntimeError):
                check_removed({**good, key: ['residual']}, True)

    def test_loaded_idle_only(self):
        good = dict(overlays={PACKAGE + '_image_1': 'applied'}, zocl_bound=['ZOCL_CU_INTC.2.auto', 'axi:zyxclmm_drm'],
                    zocl_binding_details=[dict(name='axi:zyxclmm_drm', driver='zocl-drm', path='/sys/devices/platform/axi/axi:zyxclmm_drm'),
                                          dict(name='ZOCL_CU_INTC.2.auto', driver='zocl_irq_intc', path='/sys/devices/platform/axi/axi:zyxclmm_drm/ZOCL_CU_INTC.2.auto')],
                    render_nodes=['/dev/dri/renderD128'], device_holders=[], fpga_state='operating')
        check_loaded(good)
        for key, value in [('overlays', {}), ('zocl_bound', []), ('render_nodes', []),
                           ('device_holders', [123]), ('fpga_state', 'unknown'), ('zocl_binding_details', [])]:
            with self.assertRaises(RuntimeError):
                check_loaded({**good, key: value})
        for changes in [dict(driver='unknown'), dict(path='/unrelated/ZOCL_CU_INTC.2.auto'), dict(name='unknown')]:
            broken = [good['zocl_binding_details'][0], {**good['zocl_binding_details'][1], **changes}]
            with self.assertRaises(RuntimeError):
                check_loaded({**good, 'zocl_binding_details': broken})


if __name__ == '__main__':
    unittest.main(verbosity=2)
