import base64
import json
from pathlib import Path
import tempfile
import unittest
from profile_from_uart import body, build, memory_ranges


def record(text, code=0):
    tag = 'a' * 32
    return {'raw': f'echo COMMAND_ECHO\r\nA10_{tag}_BEGIN\r\n{text}\r\nA10_{tag}_END:{code}\r\nprompt$ ',
            'completion_marker': True, 'exit_code': code}


class ProfileTests(unittest.TestCase):
    def test_strip_ansi_and_echo(self):
        self.assertEqual(body(record('\x1b[31mMemTotal\x1b[m: 123 kB')), 'MemTotal: 123 kB\n')

    def test_missing_marker(self):
        r = record('x'); r['completion_marker'] = False
        with self.assertRaises(ValueError): body(r)

    def test_mismatch_exit(self):
        r = record('x'); r['exit_code'] = 1
        with self.assertRaises(ValueError): body(r)

    def test_error_not_hidden_by_zero(self):
        self.assertIn('ERROR', body(record('modinfo: ERROR: Module zocl not found.')))

    def test_unknown_cell_counts(self):
        self.assertIsNone(memory_ranges('AAAA', None, 2))

    def test_big_endian_high_range(self):
        encoded = base64.b64encode((0x800000000).to_bytes(8, 'big') + (0x80000000).to_bytes(8, 'big')).decode()
        self.assertEqual(memory_ranges(encoded, 2, 2), [{'address_hex': '0x800000000', 'size_bytes': 2147483648}])

    def test_bad_reg(self):
        with self.assertRaises(ValueError): memory_ranges('AAAA', 2, 2)

    def test_empty_profile_not_pass(self):
        p = build([])
        self.assertIsNone(p['memory_kib']['MemTotal'])
        self.assertEqual(p['board_compute'], 'NOT_TESTED')
        self.assertIsNone(p['bo_budget_bytes'])

    def test_duplicate_and_unclosed_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'capture.json'
            doc = {'schema': 'A10_UART_READONLY_V1', 'domain': 'BOARD_READONLY',
                   'status': 'COLLECTED_REVIEW_REQUIRED', 'closed': True, 'utc': 'fixture',
                   'records': [dict(name='identity', **record('fixture'))]}
            path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError): build([path, path])
            doc['closed'] = False; path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError): build([path])


if __name__ == '__main__':
    unittest.main()
