import tempfile
from pathlib import Path
import unittest
from prepare import once, repair, prepare


class CandidateTests(unittest.TestCase):
    def test_reject_missing_and_duplicate_anchor(self):
        for text in ['absent', 'x x']:
            with self.assertRaises(ValueError):
                once(text, 'x', 'y')

    def test_reject_unknown_file(self):
        with self.assertRaises(ValueError):
            repair('other.c', '')

    def test_mapcount_fix_is_narrow(self):
        original = 'before\n\t\tfor (i = 0; i < irqc->root_domain->mapcount; i++) {\nafter'
        fixed = repair('drivers/irqchip/irq-xilinx-intc.c', original)
        self.assertIn('i < irqc->nr_irq', fixed)
        self.assertTrue(fixed.startswith('before\n'))
        self.assertTrue(fixed.endswith('\nafter'))

    def test_bad_hash_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            (source / 'drivers/of').mkdir(parents=True)
            (source / 'drivers/of/irq.c').write_text('wrong', encoding='utf-8')
            output = Path(tmp) / 'output'
            with self.assertRaises(ValueError):
                prepare(source, output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
