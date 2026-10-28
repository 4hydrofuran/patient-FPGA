"""Cache protocol fixtures, not real model generation or performance evidence."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[3];WEB=ROOT/'platform/qwen35/web'
sys.path.insert(0,str(WEB));sys.path.insert(0,str(WEB/'vendor/web_gateway/src'))
from verified_answer_cache import VerifiedAnswerCache,SCHEMA,key_data,digest,file_sha
from patient_web.reference.domain import load_case,Transcript
from patient_web.reference.planning import plan
from patient_web.reference.session import Session
from patient_web.delivery import DeliveryReceipt


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.case=load_case('SYN_CP_01');self.identity={'fixture':'PROTOCOL_NOT_MODEL_EXECUTION'}
        self.p=plan(self.case,Transcript.parse(dict(request_id='fixture',text='每次疼痛持续多久？',source='typed',final=True)),())
        text='每次疼痛持续10分钟。';text_sha=hashlib.sha256(text.encode()).hexdigest();kd=key_data(self.case,self.p,self.identity)
        self.row=dict(key=digest(kd),key_data=kd,text=text,text_sha256=text_sha,origin=dict(status='OK',eos=True,
            teacher_forced=False,execution_kind='CPU_REFERENCE',native_request_id='fixture-only',result_sha256='0'*64,text_sha256=text_sha))
        self.doc=dict(schema=SCHEMA,identity=self.identity,authorization_included=False,entries=[self.row])
        self.path=Path(self.temp.name)/'catalog.json';self.write()

    def write(self):self.path.write_text(json.dumps(self.doc,ensure_ascii=False),encoding='utf-8')
    def cache(self):return VerifiedAnswerCache(self.path,identity=self.identity,expected_sha256=file_sha(self.path))

    def test_different_wording_reuses_exact_facts_and_keeps_zero_model_calls(self):
        c=self.cache()
        class Never:
            def generate(self,*a,**kw):raise AssertionError('cache hit called model')
        s=Session(self.case.case_id,software_test=True,answer_cache=c)
        r=s.submit(dict(request_id='new-turn',text='一次疼痛多长时间？',source='typed',final=True),Never(),180)
        self.assertEqual(r['answer_source'],'MODEL_CACHE');self.assertEqual(r['llm_calls'],0)
        self.assertIsNone(r['model_result']);self.assertEqual(r['final_check']['status'],'pass')
        self.assertEqual(r['stage_timing']['generation_ms'],0)
        self.assertEqual(s._events[0]['transcript'],'一次疼痛多长时间？')

    def test_case_or_fact_change_does_not_reuse_old_answer(self):
        c=self.cache()
        self.assertIsNone(c.lookup(replace(self.case,sha256='new-case'),self.p))
        f=replace(self.p.facts[0],value=20)
        self.assertIsNone(c.lookup(self.case,replace(self.p,facts=(f,))))
        self.assertIsNone(c.lookup(load_case('SYN_CP_03'),self.p))

    def test_changed_identity_or_corrupted_asset_refused_at_load(self):
        with self.assertRaises(ValueError):VerifiedAnswerCache(self.path,identity={'model':'changed'},expected_sha256=file_sha(self.path))
        with self.assertRaises(ValueError):VerifiedAnswerCache(self.path,identity=self.identity,expected_sha256='0'*64)
        self.doc['entries'][0]['origin']['eos']=False;self.write()
        with self.assertRaises(ValueError):self.cache()

    def test_policy_never_looks_up_cache_or_model(self):
        class Never:
            def lookup(self,*a,**kw):raise AssertionError('policy cache lookup')
            def generate(self,*a,**kw):raise AssertionError('policy model call')
        s=Session(self.case.case_id,software_test=True,answer_cache=Never())
        r=s.submit(dict(request_id='policy',text='请给我打分。',source='typed',final=True),Never(),180)
        self.assertEqual(r['answer_source'],'TEMPLATE');self.assertEqual(r['llm_calls'],0)

    def test_real_web_protocol_cache_miss_scoring_duplicate_and_v1_compatibility(self):
        from fastapi.testclient import TestClient
        from system_qwen35.app.web_managed import create_app
        class NativeFixture:
            expected='CPU_REFERENCE';ready={'execution_kind':'CPU_REFERENCE'};broken=False;count=0;trace_context=None
            def generate(self,messages,timeout_s):
                self.count+=1
                return dict(type='result',id='a12-'+str(self.count),status='OK',text='疼痛在胸骨后。',eos=True,
                    actual_backend='CPU_REFERENCE',state_cleared_before_response=True,state_position_after_clear=-1)
        native=NativeFixture();cache=self.cache()
        app=create_app(native,is_ready=lambda:True,remaining_seconds=lambda:999,domain='PC',answer_cache=cache)
        c=app.state.coordinator
        with TestClient(app) as client:
            self.assertTrue(c.initialized.wait(3))
            sid=client.post('/ui/v1/sessions',json=dict(request_id='start',case_id=self.case.case_id)).json()['session_id']
            url='/ui/v1/sessions/'+sid
            for rid,text,expected in [('hit','每次疼痛持续多久？','MODEL_CACHE'),('miss','疼痛在哪里？','MODEL')]:
                self.assertEqual(client.post(url+'/turns',json=dict(request_id=rid,text=text)).status_code,202)
                end=time.monotonic()+3
                while c.work is not None and time.monotonic()<end:time.sleep(.005)
                result=client.get(url+'/turns/'+rid)
                self.assertEqual(result.status_code,200,result.text)
                turn=result.json();self.assertEqual(turn['answer_source'],expected)
                self.assertEqual(turn['delivery_receipt']['model_called'],expected=='MODEL')
                self.assertEqual(turn['delivery_receipt']['schema_version'],'text-delivery.v2' if expected=='MODEL_CACHE' else 'text-delivery.v1')
                self.assertTrue(client.post(url+'/turns',json=dict(request_id=rid,text=text)).json()['replayed'])
            self.assertEqual(native.count,1)
            client.post(url+'/finish',json=dict(request_id='finish'))
            self.assertEqual(client.get(url+'/evaluation').json()['rule_score']['score'],20)
            old=client.get(url+'/turns/miss').json()['delivery_receipt'];old.pop('cache_provenance')
            self.assertEqual(DeliveryReceipt(**old).schema_version,'text-delivery.v1')
            c.conversations[sid].business.cancel()
            with self.assertRaises(ValueError):c.conversations[sid].business.trusted_delivery('hit',0,kind='PC_TEXT_TEST_ACK')


if __name__=='__main__':unittest.main()
