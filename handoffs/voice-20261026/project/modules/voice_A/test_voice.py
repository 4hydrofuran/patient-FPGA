import json,tempfile,unittest
from pathlib import Path
from .worker import Spool
from system_qwen35.app.audio_adapter import HalfDuplex
from system_qwen35.app.planning import plan
from system_qwen35.app.domain import Transcript,load_case
from system_qwen35.app.scoring import evidence,score
from system_qwen35.app.session import Session
from system_qwen35.app.domain import digest
class Paths(unittest.TestCase):
    def test_path_boundaries(self):
        with tempfile.TemporaryDirectory() as d:
            s=Spool(d)
            for p in ('../a','/a','other/a','https://a','s\\a'):
                with self.subTest(path=p),self.assertRaises(ValueError):s.path(p,'s')
            self.assertEqual(s.path('s/a.wav','s'),Path(d)/'s/a.wav')
    def test_spool_quota(self):
        with tempfile.TemporaryDirectory() as d:
            s=Spool(d)
            with self.assertRaises(ValueError):s.budget(64*1024*1024+1)
    def test_file_count(self):
        with tempfile.TemporaryDirectory() as d:
            s=Spool(d);s.MAX_FILES=2
            for n in ('a','b'):(Path(d)/n).touch()
            with self.assertRaises(ValueError):s.budget()
    def test_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            s=Spool(d);(Path(d)/'s').symlink_to('/tmp')
            with self.assertRaises(ValueError):s.path('s/file','s')
class State(unittest.TestCase):
    def test_order(self):
        m=HalfDuplex()
        for state in m.ORDER[1:]:self.assertTrue(m.advance(state,0))
        self.assertEqual(m.state,'READY')
    def test_no_listen_during_play(self):
        m=HalfDuplex()
        for state in m.ORDER[1:-1]:m.advance(state,0)
        with self.assertRaises(RuntimeError):m.advance('LISTENING',0)
    def test_stale_results(self):
        m=HalfDuplex();m.advance('LISTENING',0);m.cancel()
        self.assertFalse(m.advance('ASR_FINAL',0));self.assertEqual(m.state,'READY')
    def test_partial_display_only(self):
        m=HalfDuplex();m.advance('LISTENING',0);m.display_partial('不是没有',0)
        self.assertEqual(m.partial,'不是没有');self.assertEqual(m.played,[])
        m.cancel();m.display_partial('迟到',0);self.assertEqual(m.partial,'')
    def test_unknown_confidence_not_invented(self):
        t=Transcript.parse(dict(request_id='x',text='哪里痛',source='asr_final',final=True,confidence=None))
        c=load_case('SYN_CP_01')
        self.assertEqual(plan(c,t,()).route,'clarify')
        confirmed=plan(c,t,(),asr_confirmed=True)
        self.assertEqual(confirmed.route,'answer')
        e=evidence(t,confirmed,1);self.assertTrue(e['requires_review']);self.assertEqual(score([e])['score'],0)
    def test_low_confidence_still_review(self):
        t=Transcript.parse(dict(request_id='x',text='哪里痛',source='asr_final',final=True,confidence=.4))
        self.assertEqual(plan(load_case('SYN_CP_01'),t,(),asr_confirmed=True).route,'clarify')
    def test_receipt_is_not_acoustic_measurement(self):
        s=Session('SYN_CP_01',software_test=True)
        r=s.submit(dict(request_id='receipt',text='哪里痛',source='asr_final',confidence=None,final=True),None)
        self.assertEqual(r['answer_source'],'TEMPLATE')
        receipt=dict(cancelled=False,playback_api_completed=True,text_digest=digest(r['text']))
        s.trusted_playback_delivery('receipt',s.epoch,receipt)
        p=s.snapshot()['played'][0]
        self.assertIsNone(p['audio_played']);self.assertFalse(p['acoustic_verified'])
    def test_partial_playback_never_commits(self):
        s=Session('SYN_CP_01',software_test=True)
        r=s.submit(dict(request_id='receipt',text='哪里痛',source='asr_final',confidence=None,final=True),None)
        with self.assertRaises(ValueError):s.trusted_playback_delivery('receipt',s.epoch,dict(cancelled=True,playback_api_completed=False,text_digest=digest(r['text'])))
        self.assertEqual(s.snapshot()['played'],[])
        epoch=s.epoch;s.cancel()
        with self.assertRaises(ValueError):s.trusted_playback_delivery('receipt',epoch,dict(cancelled=False,playback_api_completed=True,text_digest=digest(r['text'])))
    def test_confirmation_does_not_rewrite_transcript(self):
        s=Session('SYN_CP_01',software_test=True)
        with self.assertRaises(ValueError):s.submit(dict(request_id='x',text='哪里痛',source='asr_final',confidence=None,final=True),None,trusted_asr_confirmation={'kind':'SYNTHETIC_FIXTURE_EXACT_TRANSCRIPT','raw_text_digest':digest('其他问题')})
    def test_human_confirmation_explicit_gate(self):
        s=Session('SYN_CP_01',software_test=True)
        with self.assertRaises(ValueError):s.submit(dict(request_id='x',text='您好',source='asr_final',confidence=None,final=True),None,trusted_asr_confirmation={'kind':'HUMAN_VERIFIED_RAW_TRANSCRIPT','raw_text_digest':digest('您好'),'human_review':False})
    def test_human_confirmation_does_not_fabricate_confidence(self):
        s=Session('SYN_CP_01',software_test=True)
        r=s.submit(dict(request_id='x',text='您好',source='asr_final',confidence=None,final=True),None,trusted_asr_confirmation={'kind':'HUMAN_VERIFIED_RAW_TRANSCRIPT','raw_text_digest':digest('您好'),'human_review':True})
        self.assertEqual(r['asr_confirmation']['kind'],'HUMAN_VERIFIED_RAW_TRANSCRIPT')
        self.assertIsNone(s.snapshot()['received'][0]['confidence']);self.assertEqual(s.recompute_score_for_host()['score'],0)
if __name__=='__main__':unittest.main(verbosity=2)
