import base64
import hashlib
import unittest
from peer_capture import payload


class CaptureTests(unittest.TestCase):
    def record(self, data, encoded=True):
        tag = "a" * 32
        body = base64.b64encode(data).decode() + "\n" if encoded else data.decode()
        raw = "echo: printf 'A10_fake_BEGIN'\nA10_" + tag + "_BEGIN\n" + body + "\nA10_" + tag + "_END:0\n"
        return dict(raw=raw.replace("\n", "\r\n"), exit_code=0, completion_marker=True)

    def check(self, record, data, encoded=True):
        return payload(record, len(data), hashlib.sha256(data).hexdigest(), encoded=encoded)

    def test_binary_is_exact(self):
        data = bytes(range(256))
        self.assertEqual(self.check(self.record(data), data), data)

    def test_json_with_and_without_final_newline(self):
        for data in (b'{"n":32}', b'{"n":32}\n'):
            self.assertEqual(self.check(self.record(data, False), data, False), data)

    def test_bad_digest_is_rejected(self):
        with self.assertRaises(ValueError):
            self.check(self.record(b"old"), b"new")

    def test_failed_or_incomplete_read_is_rejected(self):
        for change in (dict(exit_code=1), dict(exit_code=None), dict(completion_marker=False)):
            row = self.record(b"ok")
            row.update(change)
            with self.assertRaises(ValueError):
                self.check(row, b"ok")

    def test_duplicate_marker_is_rejected(self):
        row = self.record(b"ok")
        row["raw"] += row["raw"]
        with self.assertRaises(ValueError):
            self.check(row, b"ok")

    def test_malformed_base64_is_rejected(self):
        row = self.record(b"ok")
        row["raw"] = row["raw"].replace("b2s=", "b2s=!")
        with self.assertRaises(ValueError):
            self.check(row, b"ok")


if __name__ == "__main__":
    unittest.main()
