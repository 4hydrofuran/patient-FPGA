import stat
import unittest
from inspect_initramfs_layout import newc
from prepare_boot_candidate import entry, filter_old_modules, closure, OLD, safe_name
from audit_boot_candidate import archive_name, RELEASE


class BootCandidateTests(unittest.TestCase):
    def test_module_archive_scope(self):
        self.assertEqual(archive_name('lib/modules/'+RELEASE+'/extra/zocl.ko'), 'extra/zocl.ko')
        for name in ('etc/shadow', 'lib/modules/old/x.ko', 'lib/modules/'+RELEASE+'/../../key.pem'):
            with self.assertRaises(ValueError):
                archive_name(name)

    def test_roundtrip(self):
        raw = entry('usr/a', b'abcd', stat.S_IFREG|0o644, 1) + entry('TRAILER!!!', b'', 0, 0)
        rows, end = newc(raw)
        self.assertEqual(end, len(raw))
        self.assertEqual(raw[rows[0]['data_start']:rows[0]['data_end']], b'abcd')

    def test_only_old_module_tree_removed(self):
        kept = entry('init', b'not executed', stat.S_IFREG|0o755, 4)
        removed = entry(OLD+'/modules.dep', b'old', stat.S_IFREG|0o644, 5)
        raw, count = filter_old_modules(kept + removed + entry('TRAILER!!!', b'', 0, 0))
        self.assertEqual(count, 1)
        self.assertTrue(raw.startswith(kept))
        self.assertEqual([e['path'] for e in newc(raw)[0]], ['init'])

    def test_unexpected_archive_tail_rejected(self):
        with self.assertRaises(ValueError):
            filter_old_modules(entry('TRAILER!!!', b'', 0, 0) + b'unknown')

    def test_truncation(self):
        for raw in (b'', b'070701', entry('a', b'abc', stat.S_IFREG|0o644, 1)[:-3]):
            with self.assertRaises(ValueError):
                newc(raw)

    def test_unsafe_path(self):
        for name in ('', '../a', '/absolute', 'a/../escape', 'bad\0name', 'a\\b'):
            with self.assertRaises(ValueError):
                safe_name(name)

    def test_closure_and_missing(self):
        self.assertEqual(closure(['a'], {'a':['b'], 'b':['a', 'c'], 'c':[]}), ['a','b','c'])
        with self.assertRaisesRegex(ValueError, 'Missing module'):
            closure(['missing'], {})

    def test_hardlink_metadata_preserved(self):
        first = bytearray(entry('one', b'body', stat.S_IFREG|0o644, 42))
        first[38:46] = b'00000002'
        other = bytearray(entry('two', b'', stat.S_IFREG|0o644, 42))
        other[38:46] = b'00000002'
        original = bytes(first+other) + entry('TRAILER!!!', b'', 0, 0)
        result, count = filter_old_modules(original)
        self.assertEqual(count, 0)
        self.assertEqual(result, original)


if __name__ == '__main__':
    unittest.main()
