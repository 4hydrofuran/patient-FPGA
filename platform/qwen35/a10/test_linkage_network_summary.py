import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from summarize_linkage_network import summarize

ROOT = Path(__file__).resolve().parents[3] / "evidence/board_platform/A10_20261018_intake"


class EvidenceTests(unittest.TestCase):
    def test_real_sources_narrow_status(self):
        r = summarize(ROOT)
        self.assertEqual(r["linkage_only"]["status"], "PASS")
        self.assertEqual(r["BOARD_compute"], "NOT_TESTED")
        self.assertEqual(r["real_comparisons"], 0)
        self.assertFalse(r["pl_load_authorized"])
        self.assertIsNone(r["BO_reachability"])
        self.assertEqual(r["temporary_network"]["address"], "192.168.2.2/24")
        for lib in r["xrt_sections"].values():
            self.assertEqual(set(lib["different_sections"]), {".note.gnu.build-id", ".rodata", ".gnu_debuglink"})

    def mutate(self, filename, change):
        original = Path.read_bytes

        def altered(path):
            data = original(path)
            if path.name == filename:
                obj = json.loads(data.decode("utf-8-sig"))
                change(obj)
                return json.dumps(obj).encode()
            return data

        with patch.object(Path, "read_bytes", altered), self.assertRaises(ValueError):
            summarize(ROOT)

    def test_failure_not_accepted(self):
        self.mutate("uart_linkage_once_01.json", lambda o: o.update(exit_code=124))

    def test_changed_boot_rejected(self):
        self.mutate("ssh_platform_inventory_01.json", lambda o: o.update(boot_id="different-boot"))

    def test_missing_readback_rejected(self):
        self.mutate("uart_temporary_ip_add_01.json", lambda o: o.update(raw=o["raw"].replace("192.168.2.2/24", "192.168.2.3/24")))

    def test_null_timing_not_zero(self):
        self.mutate("uart_linkage_once_01.json", lambda o: o.update(exit_code=None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
