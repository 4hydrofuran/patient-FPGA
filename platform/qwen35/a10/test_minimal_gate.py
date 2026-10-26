import unittest
import struct
from minimal_gate import MinimalGate, PREFIX, TEST_PROPERTIES, DEFAULT_PROPERTIES, IRQ_END
from kernel_log_gate import digest


class GateTests(unittest.TestCase):
    def gate(self):
        g = MinimalGate()
        raw = '<6>[ 0.1] baseline\n'
        self.assertTrue(g.observe_action('boot', raw, digest(raw), 'none')['allowed'])
        return g, raw

    def test_exact_properties_scoped(self):
        for action, paths in [('load_test', TEST_PROPERTIES), ('load_default', DEFAULT_PROPERTIES)]:
            g, raw = self.gate()
            raw += ''.join('<3>[ 1.1] ' + PREFIX + p + '\n' for p in paths)
            r = g.observe_action('boot', raw, None, action)
            self.assertTrue(r['allowed'])
            self.assertEqual(len(r['reviewed_advisories']), len(paths))

    def test_real_faults_latch(self):
        for msg in ['OF: ERROR: memory leak, expected refcount 1 instead of 65',
                    'zocl-drm axi:zyxclmm_drm: error -ENXIO: IRQ index 32 not found',
                    'Oops: kernel fault', PREFIX + '/unknown']:
            g, raw = self.gate()
            self.assertFalse(g.observe_action('boot', raw + '<3>[ 1.1] ' + msg + '\n',
                                             None, 'load_test')['allowed'])
            self.assertFalse(g.observe_action('boot', raw, digest(raw), 'none')['allowed'])

    def test_wrong_action_and_duplicates(self):
        line = '<3>[ 1.1] ' + PREFIX + TEST_PROPERTIES[0] + '\n'
        for action, suffix in [('remove', line), ('load_test', line + line)]:
            g, raw = self.gate()
            self.assertFalse(g.observe_action('boot', raw + suffix, None, action)['allowed'])

    def test_boot_and_continuity(self):
        g, raw = self.gate()
        self.assertFalse(g.observe_action('other', raw, None, 'none')['allowed'])
        g, raw = self.gate()
        self.assertFalse(g.observe_action('boot', '<6>[ 2.0] truncated\n', None, 'none')['allowed'])

    def test_external_module_scope(self):
        g, raw = self.gate()
        self.assertTrue(g.observe_action('boot', raw +
            '<4>[ 2.0] zocl: loading out-of-tree module taints kernel.\n', None, 'insmod')['allowed'])

    def test_unreviewed_baseline(self):
        self.assertFalse(MinimalGate().observe_action(
            'boot', '<3>[ 0.1] error\n', None, 'load_test')['allowed'])

    def test_irq_sentinel_needs_dt_and_scope(self):
        for action, verified, expected in [('load_test', True, True),
                                           ('load_test', False, False),
                                           ('remove', True, False)]:
            g, raw = self.gate()
            self.assertEqual(g.observe_action('boot', raw + '<3>[ 3.0] ' + IRQ_END + '\n',
                                             None, action, verified)['allowed'], expected)

    def test_exact_irq_descriptors(self):
        from minimal_continue import decode_irq_descriptors
        raw = b''.join(struct.pack('>III', 99, i, 4) for i in range(32))
        self.assertEqual(len(decode_irq_descriptors(raw, 99, 2)), 32)
        for data, parent, cells in [(raw[:-12], 99, 2), (raw, 98, 2), (raw, 99, 1),
                                    (raw[:12] + raw[:12] + raw[24:], 99, 2)]:
            with self.assertRaises(RuntimeError):
                decode_irq_descriptors(data, parent, cells)


if __name__ == '__main__':
    unittest.main()
