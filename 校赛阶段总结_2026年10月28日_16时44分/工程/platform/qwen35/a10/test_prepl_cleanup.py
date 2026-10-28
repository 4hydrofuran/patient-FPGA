import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import cleanup_prepl_isolated_once as cleanup
import fetch_isolated_result as fetch


class CleanupTests(unittest.TestCase):
    def test_exact_preserved_log_is_prepl_only(self):
        root = Path(__file__).resolve().parents[3]
        raw = (root/'evidence/board_platform/A10_20261023_isolated_idle_v1/parked_readback_01/lifecycle.jsonl').read_bytes()
        cleanup.validate_log(raw)
        with self.assertRaisesRegex(RuntimeError, 'log changed'):
            cleanup.validate_log(raw + b'{}\n')
        # Even a reviewed changed hash must not admit an actual PL command.
        extra = raw + b'{"event":"COMMAND_BEGIN"}\n'
        with patch.object(cleanup, 'LOG_SHA', hashlib.sha256(extra).hexdigest()):
            with self.assertRaisesRegex(RuntimeError, 'hardware/unknown'):
                cleanup.validate_log(extra)

    def test_default_plan_is_readonly_and_pinned(self):
        with patch.object(fetch.subprocess, 'Popen', side_effect=AssertionError('no connection')):
            readonly, _ = fetch.plan()
            recovery, _ = fetch.plan(cleanup=True)
        self.assertIn('reviewed_read_isolated_result.py', readonly[-1])
        self.assertIn('reviewed_cleanup_prepl_isolated_once.py', recovery[-1])
        self.assertIn('StrictHostKeyChecking=yes', recovery)
        self.assertNotIn('SIGKILL', Path(cleanup.__file__).read_text().split('import hashlib',1)[1])


if __name__ == '__main__':
    unittest.main()
