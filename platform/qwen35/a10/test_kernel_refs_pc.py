import unittest
from audit_kernel_refs_pc import reference_model, remove_model, function


class OwnershipModels(unittest.TestCase):
    def test_extended_reference_leak(self):
        self.assertEqual(reference_model(True, 32), 33)
        self.assertEqual(reference_model(True, 32, 2), 65)

    def test_legacy_reference_balanced(self):
        self.assertEqual(reference_model(False, 32, 2), 1)

    def test_empty_has_no_ref_change(self):
        self.assertEqual(reference_model(True, 0, 2), 1)

    def test_shrinking_bound_leaves_half(self):
        self.assertEqual(remove_model(range(32), 32, False)['remaining'], list(range(16, 32)))

    def test_shrinking_bound_misses_sparse_mapping(self):
        self.assertEqual(remove_model([31], 32, False)['remaining'], [31])

    def test_fixed_bound_model_handles_full_sparse_empty(self):
        for mapping in [range(32), [0, 31], [31], []]:
            self.assertEqual(remove_model(mapping, 32, True)['remaining'], [])

    def test_function_location(self):
        found = function('/* prefix */\nint example(int x)\n{\n if (x) { return 1; }\n return 0;\n}\n', 'example')
        self.assertEqual(found['line'], 2)
        self.assertIn('return 0;', found['text'])
        with self.assertRaises(ValueError):
            function('int missing(void);', 'missing')

    def test_comment_reference_not_function(self):
        source = ('/*\n * wrapper calls example() and\n * helper()\n */\n'
                  'int wrapper(void)\n{ return 9; }\n'
                  'int example(void)\n{ return 1; }\n')
        self.assertEqual(function(source, 'example')['text'], 'int example(void)\n{ return 1; }')


if __name__ == '__main__':
    unittest.main(verbosity=2)
