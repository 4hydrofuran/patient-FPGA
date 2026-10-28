"""PC policy fixtures: reject capacity before native BEGIN or credit mutation."""
import copy
import types
import unittest
from resident_manager import Manager, AdmissionDenied
from resident_board import BoardProvider, BoardService
from resident_evidence import OUT, read
from resident_service import ResidentService
from resident_cli import parse_request, InputError


class AdmissionTests(unittest.TestCase):
    def manager(self):
        m=Manager.__new__(Manager);m._guard=lambda:True;m.active=None;m.claims=360;m.cap=72
        m.journal=types.SimpleNamespace(serial=90,size=60000)
        m.stream_bytes=10000;m.stream_packets=4
        return m

    def request(self):return dict(tokens=list(range(48)),cache_policy='TT10_REQUIRE_HIT',max_tokens=24,op='generate')

    def test_worst_case_no_eos_guess(self):
        m=self.manager();self.assertEqual(m.admission(self.request()),1800)
        m.claims=3201
        with self.assertRaises(AdmissionDenied):m.admission(self.request())
        self.assertEqual(m.claims,3201)

    def test_cap_one_capacity_before_begin(self):
        m=self.manager();m.cap=1;m.journal.serial=2400
        with self.assertRaises(AdmissionDenied):m.admission(self.request())
        self.assertEqual(m.claims,360)

    def test_capacity_each_bound(self):
        for field,value in [('serial',4090),('size',4*1024*1024-8192)]:
            with self.subTest(field=field):
                m=self.manager();setattr(m.journal,field,value)
                with self.assertRaises(AdmissionDenied):m.admission(self.request())
        for field,value in [('stream_bytes',1024*1024-1024),('stream_packets',220)]:
            with self.subTest(field=field):
                m=self.manager();setattr(m,field,value)
                with self.assertRaises(AdmissionDenied):m.admission(self.request())

    def test_no_json_board_authority(self):
        with self.assertRaisesRegex(RuntimeError,'actual root ARM64'):
            BoardProvider({},OUT/'BOARD_BUILD-v1-review-only.json')
        with self.assertRaisesRegex(RuntimeError,'actual original root ARM64'):
            BoardService(OUT/'BOARD_BUILD-v1-review-only.json','unused',owner={})

    def test_input_transport_keeps_original_identity(self):
        q=parse_request(b'{"op":"submit","transcript":{"request_id":"one","text":"x","source":"typed","final":true}}')
        self.assertEqual(q['transcript']['request_id'],'one')
        for raw in (b'{"op":"acknowledge"}',b'{"op":"submit","transcript":"x"}',
                    b'{"op":"close","op":"cancel"}',b'{"op":"submit","transcript":{},"timeout_s":NaN}'):
            with self.assertRaises(InputError):parse_request(raw)


if __name__=='__main__':unittest.main()
