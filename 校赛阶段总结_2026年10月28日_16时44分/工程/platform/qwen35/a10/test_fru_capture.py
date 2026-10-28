import copy
import json
from pathlib import Path
import unittest
import audit_fru_capture as a


def fixture(record=bytes.fromhex('028203fa7f010203')):
    # Independent hand-computed multirecord: 1+2+3+FA=0; header sum=0.
    common=bytes.fromhex('01000001000400fa')
    board=bytearray(bytes.fromhex('010300000000')+b'\xc2AB\xc2CD\xc2EF\xc2GH\x00\xc1')
    board.extend(bytes(23-len(board)))
    board.append((-sum(board))%256)
    return common+board+record


class FruTests(unittest.TestCase):
    def test_hand_record(self):
        r=a.parse_fru(fixture())
        self.assertTrue(r['multirecord_chain_valid'])
        self.assertEqual(r['identity']['serial']['text'],'EF')
        self.assertFalse(r['eeprom_entire_contents_verified'])

    def test_common_checksum(self):
        b=bytearray(fixture());b[7]^=1
        with self.assertRaisesRegex(ValueError,'Common'):a.parse_fru(b)

    def test_board_checksum(self):
        b=bytearray(fixture());b[31]^=1
        with self.assertRaisesRegex(ValueError,'Board info checksum'):a.parse_fru(b)

    def test_truncated_board(self):
        with self.assertRaisesRegex(ValueError,'length'):a.parse_fru(fixture()[:20])

    def test_truncated_record(self):
        self.assertEqual(a.parse_fru(fixture()[:-1])['multirecord_error']['reason'],'TRUNCATED_OR_BAD_PAYLOAD')

    def test_header_checksum(self):
        b=bytearray(fixture());b[36]^=1
        self.assertEqual(a.parse_fru(b)['multirecord_error']['reason'],'INVALID_HEADER')

    def test_payload_checksum(self):
        b=bytearray(fixture());b[-1]^=1
        self.assertFalse(a.parse_fru(b)['multirecord_chain_valid'])

    def test_no_end_no_padding_skip(self):
        r=a.parse_fru(fixture(bytes.fromhex('020203faff010203')+b'\xff'*24))
        self.assertFalse(r['multirecord_chain_valid'])
        self.assertEqual(r['multirecord_error']['offset'],40)

    def test_field_overrun(self):
        b=bytearray(fixture());b[14]=0xff;b[31]=0;b[31]=(-sum(b[8:32]))%256
        with self.assertRaisesRegex(ValueError,'overruns'):a.parse_fru(b)

    def test_fixture_actual_capture(self):
        capture=json.loads((Path(__file__).resolve().parents[3]/'evidence/board_platform/A10_20261018_intake/uart_fru_kernel_readonly_01.json').read_text(encoding='utf-8-sig'))
        result=a.audit(capture)
        self.assertEqual(result['records'][0]['identity']['product']['text'],'SMK-K26-XCL2G-ED')
        self.assertEqual(result['records'][1]['identity']['product']['text'],'SCK-KV-G')
        self.assertEqual([r['multirecord_error']['offset'] for r in result['records']],[137,122])
        self.assertFalse(result['board_modified'])
        bad=copy.deepcopy(capture);bad['raw']=bad['command']
        with self.assertRaises(ValueError):a.audit(bad)
        bad=copy.deepcopy(capture);bad['exit_code']=1
        with self.assertRaises(ValueError):a.audit(bad)
        bad=copy.deepcopy(capture);bad['raw']=bad['raw'].replace('80f6c335996f','00f6c335996f')
        with self.assertRaisesRegex(ValueError,'hash'):a.audit(bad)


if __name__=='__main__':unittest.main(verbosity=2)
