import json
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/web'))
from continuous_sessions import install,may_end,question_reserve
from interactive_case import CachedTransport


class Tests(unittest.TestCase):
    def test_finished_consultation_does_not_stop_continuous_model(self):
        args=dict(closed=True,idle=True,model_requests=3,maximum_questions=None,broken=False)
        self.assertFalse(may_end(continuous=True,**args))
        self.assertTrue(may_end(continuous=True,stop_requested=True,**args))
        self.assertTrue(may_end(continuous=False,**dict(args,maximum_questions=2)))
        self.assertFalse(may_end(continuous=True,stop_requested=True,**dict(args,idle=False)))
        self.assertEqual(question_reserve(),10296)

    def test_continuous_transport_accepts_multiple_calls_without_rewarming(self):
        sent=[];worker=types.SimpleNamespace(send=sent.append)
        transport=CachedTransport(worker,object(),Path('/unused'),object(),maximum_questions=None)
        transport.binding='same-live-binding'
        for i in range(4):
            transport.send(dict(id='a12-'+str(i+1)));transport.inflight=False
        self.assertEqual(transport.questions_sent,4)
        self.assertTrue(all(q['cache_binding_sha256']=='same-live-binding' and q['cache_policy']=='TT10_REQUIRE_HIT' for q in sent))

    def test_ninth_consultation_retains_older_evaluation_and_idempotent_start(self):
        class Coordinator:
            def __init__(self):
                self.lock=threading.RLock();self.starts={};self.conversations={};self.current_session=None
                self.journal=types.SimpleNamespace(sequence=0)
            def create_session(self,rid,case):
                if rid in self.starts:return self.starts[rid]
                if len(self.conversations)>=8:raise RuntimeError('session limit')
                sid=f'{len(self.starts)+1:032x}'
                self.conversations[sid]=types.SimpleNamespace(closed=False,case=case)
                self.current_session=sid;self.journal.sequence+=1
                r=dict(session_id=sid);self.starts[rid]=r;return r
            def finish(self,sid,rid):self.conversations[sid].closed=True;return dict(status='finished')
            def snapshot(self,sid):
                c=self.conversations[sid]
                return dict(session_id=sid,case_id=c.case,closed=c.closed,turns=[],cursor=self.journal.sequence)
            def evaluation(self,sid):return dict(session_id=sid,score=10)
            def turn_result(self,sid,rid):raise KeyError(rid)
            def event_batch(self,sid,after):return [],False,self.journal.sequence
        c=Coordinator()
        with tempfile.TemporaryDirectory() as directory:
            install(c,directory)
            ids=[]
            for i in range(10):
                sid=c.create_session(str(i),'case')['session_id'];ids.append(sid);c.finish(sid,'finish')
            self.assertEqual(len(c.conversations),8)
            self.assertNotIn(ids[0],c.conversations)
            self.assertEqual(c.create_session('0','case')['session_id'],ids[0])
            self.assertTrue(c.snapshot(ids[0])['closed'])
            self.assertEqual(c.evaluation(ids[0])['score'],10)
            self.assertEqual(c.event_batch(ids[0],0),([],False,c.journal.sequence))
            self.assertEqual(len(list(Path(directory).glob('*.json'))),10)


if __name__=='__main__':unittest.main()
