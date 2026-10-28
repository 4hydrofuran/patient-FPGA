import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("summary", Path(__file__).with_name("summarize_driver_board.py"))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class SummaryTests(unittest.TestCase):
    def test_no_command_echo_as_output(self):
        capture = {"exit_code": 0, "raw": "printf 'A10_123_BEGIN'; claimed_pass\r\nA10_123_BEGIN\r\nactual\r\nA10_123_END:0\r\n"}
        self.assertEqual(s.output_text(capture).strip(), "actual")

    def test_missing_marker_refused(self):
        with self.assertRaises(ValueError):
            s.output_text({"exit_code": 0, "raw": "printf 'A10_123_BEGIN'; echoed_command_only"})

    def test_rc_mismatch_refused(self):
        with self.assertRaises(ValueError):
            s.output_text({"exit_code": 0, "raw": "A10_123_BEGIN\nactual\nA10_123_END:1\n"})

    def test_ansi_and_repeated_cr(self):
        self.assertEqual(s.output_text({"exit_code": 0, "raw": "A10_abc_BEGIN\r\r\n\x1b[31mactual\x1b[m\r\r\nA10_abc_END:0\r\n"}).strip(), "actual")


if __name__ == "__main__":
    unittest.main(verbosity=2)
