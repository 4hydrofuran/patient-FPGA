import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import stage_candidate_board as s


class StagingTests(unittest.TestCase):
    def member(self, suffix="kernel/x.ko", size=4):
        t = tarfile.TarInfo("lib/modules/" + s.RELEASE + "/" + suffix)
        t.size = size
        return t

    def test_exact_tree_only(self):
        self.assertEqual(str(s.relative_member(self.member())), "kernel/x.ko")
        for path in ("/tmp/x.ko", "lib/modules/old/x.ko", "../x.ko",
                     "lib/modules/" + s.RELEASE + "/../../etc/x.ko"):
            t = self.member(); t.name = path
            with self.assertRaises(ValueError):
                s.relative_member(t)

    def test_links_and_devices_rejected(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.CHRTYPE):
            t = self.member(); t.type = kind
            with self.assertRaises(ValueError):
                s.relative_member(t)

    def test_unknown_files_and_size_rejected(self):
        for t in (self.member("key.pem"), self.member(size=s.MAX_FILE + 1),
                  self.member("kernel/./x.ko"), self.member("kernel\\x.ko")):
            with self.assertRaises(ValueError):
                s.relative_member(t)

    def archive(self, root, duplicate=False):
        p = root / "test.tar.gz"
        with tarfile.open(p, "w:gz") as tar:
            names = ["kernel/x.ko", "modules.dep", "modules.dep.bin", "modules.alias", "modules.alias.bin"]
            if duplicate:
                names.append("kernel/x.ko")
            for name in names:
                tar.addfile(self.member(name), io.BytesIO(b"abcd"))
        return p

    def test_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive = self.archive(root); dest = root / "new"
            result = s.unpack_modules(archive, dest, s.Limiter(rate=10**10), 1)
            self.assertEqual(result["modules"], 1)
            self.assertEqual(result["bytes"], 20)
            with self.assertRaises(ValueError):
                s.unpack_modules(archive, dest, s.Limiter(), 1)
            self.assertEqual((dest / "kernel/x.ko").read_bytes(), b"abcd")

    def test_duplicate_retained_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive = self.archive(root, True); dest = root / "partial"
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                s.unpack_modules(archive, dest, s.Limiter(rate=10**10), 1)
            self.assertTrue(dest.exists())

    def test_wrong_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                s.unpack_modules(self.archive(root), root / "partial", s.Limiter(rate=10**10), 2)

    def test_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(s, "MAX_TOTAL", 2), self.assertRaisesRegex(ValueError, "budget"):
                s.unpack_modules(self.archive(root), root / "partial", s.Limiter(), 1)

    def test_readback_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive = self.archive(root); dest = root / "partial"
            with patch.object(s, "digest", return_value="mismatch"), self.assertRaisesRegex(ValueError, "readback"):
                s.unpack_modules(archive, dest, s.Limiter(rate=10**10), 1)
            self.assertTrue(dest.exists())

    def test_health_stop_preserves_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive = self.archive(root); dest = root / "partial"
            def failed_health():
                raise ValueError("thermal guard")
            with self.assertRaisesRegex(ValueError, "thermal"):
                s.unpack_modules(archive, dest, s.Limiter(rate=10**10, health=failed_health), 1)
            self.assertTrue(dest.is_dir())

    def test_limiter_does_not_skip_long_wait(self):
        clock = [0.0]
        def advance(seconds):
            clock[0] += seconds
        with patch.object(s.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(s.time, "sleep", side_effect=advance):
            limiter = s.Limiter(rate=4)
            limiter.add(8)
        self.assertGreaterEqual(clock[0], 2)

    def test_health_logging_bounded_during_many_small_writes(self):
        clock = [0.0]
        calls = []
        def advance(seconds):
            clock[0] += seconds
        with patch.object(s.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(s.time, "sleep", side_effect=advance):
            limiter = s.Limiter(rate=1000, health=lambda: calls.append(clock[0]))
            for _ in range(1000):
                limiter.add(10)
        self.assertGreaterEqual(clock[0], 10)
        self.assertGreaterEqual(len(calls), 4)
        self.assertLessEqual(len(calls), 6)
        self.assertTrue(all(b-a >= 2 for a,b in zip(calls,calls[1:])))

    @unittest.skipUnless(os.name == "posix", "Linux renameat2 only")
    def test_atomic_noreplace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); a = root / "a"; b = root / "b"
            a.mkdir(); b.mkdir()
            with self.assertRaises(OSError):
                s.rename_noreplace(a, b)
            self.assertTrue(a.is_dir())
            self.assertTrue(b.is_dir())
            c = root / "c"; s.rename_noreplace(a, c)
            self.assertTrue(c.is_dir())
            self.assertFalse(a.exists())

    def test_default_plan_no_boot(self):
        p = s.plan()
        self.assertFalse(p["QSPI_write"] or p["default_boot_change"] or p["module_load"])
        self.assertNotEqual(Path(p["candidate_fit"]).name, "image.fit")
        self.assertEqual(p["io_rate_bytes_s"], 8 * 1024**2)


if __name__ == "__main__":
    unittest.main()
