import unittest
from repair_intc_data_owner import repair


class OwnershipTests(unittest.TestCase):
    def test_both_free_paths_clear_only_owned_pointer(self):
        anchor = '\tiounmap(irqc->base);\n\tkfree(irqc);'
        result = repair('error:\n' + anchor + '\nremove:\n' + anchor)
        self.assertEqual(result.count('if (intc->data == irqc)'), 2)
        self.assertEqual(result.count('intc->data = NULL;'), 2)
        self.assertEqual(result.count('kfree(irqc);'), 2)
        for part in result.split('kfree(irqc);')[:-1]:
            self.assertLess(part.index('intc->data = NULL;'), part.index('iounmap'))

    def test_no_blind_reapply_or_unknown_source_shape(self):
        for raw in ('', '\tiounmap(irqc->base);\n\tkfree(irqc);'):
            with self.assertRaises(ValueError):
                repair(raw)


if __name__ == '__main__':
    unittest.main()
