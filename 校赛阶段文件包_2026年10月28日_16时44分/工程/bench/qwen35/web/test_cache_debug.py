"""Next-consultation answer-cache control and stable mode labels, PC fixtures."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[3];WEB=ROOT/'platform/qwen35/web'
sys.path.insert(0,str(WEB));sys.path.insert(0,str(WEB/'integrated/B_601e69ca_A_case20_debug_20261027/web_gateway/src'))
from fastapi.testclient import TestClient
from patient_web.api import create_app
from patient_web.managed import ManagedPLEngine
from verified_answer_cache import VerifiedAnswerCache,file_sha
from natural_patient_prompt import prompt_messages
from continuous_sessions import install

class NativeFixture:
    broken=False;count=0;trace_context=None
    def __init__(self,kind):self.expected=kind;self.ready={'execution_kind':kind}
    def generate(self,messages,timeout_s):
        self.count+=1
        return dict(type='result',id='a12-'+str(self.count),status='OK',eos=True,
            text=messages[-1]['content'].split('\n',1)[1],actual_backend=self.expected,
            state_cleared_before_response=True,state_position_after_clear=-1)

class Tests(unittest.TestCase):
    def setUp(self):
        p=ROOT/'evidence/model_pl_A/20261027-case20-natural-v1/full1320/catalog.json'
        identity=json.loads(p.read_text(encoding='utf-8'))['identity']
        self.cache=VerifiedAnswerCache(p,identity=identity,expected_sha256=file_sha(p))
        self.cpu=NativeFixture('CPU_REFERENCE');self.fpga=NativeFixture('FPGA_REAL')
    def engine(self,native,cache):
        return ManagedPLEngine(native,is_ready=lambda:True,prompt_builder=prompt_messages,answer_cache=cache,
            domain='PC' if native is self.cpu else 'BOARD')
    def answer(self,client,sid,rid):
        self.assertEqual(client.post('/ui/v1/sessions/'+sid+'/turns',json={'request_id':rid,'text':'疼痛在什么位置？'}).status_code,202)
        end=time.monotonic()+5
        while time.monotonic()<end:
            r=client.get('/ui/v1/sessions/'+sid+'/turns/'+rid).json()
            if r['status']!='RUNNING':return r
            time.sleep(.01)
        self.fail('fixture answer deadline')
    def test_hit_and_miss_apply_only_when_creating_next_consultation(self):
        app=create_app(backend='native',engine_factory=lambda:self.engine(self.cpu,self.cache))
        with tempfile.TemporaryDirectory() as d:
            install(app.state.coordinator,Path(d))
            with TestClient(app) as c:
                self.assertTrue(app.state.coordinator.initialized.wait(3))
                hit=c.post('/ui/v1/sessions',json={'request_id':'hit','cache_mode':'hit'}).json();sid=hit['session_id']
                a=self.answer(c,sid,'hit-turn');self.assertEqual(a['answer_source'],'MODEL_CACHE');self.assertEqual(a['execution_mode'],'CPU')
                self.assertFalse(a['delivery_receipt']['model_called']);self.assertIsNone(a['actual_backend'])
                self.assertEqual(self.cpu.count,0)
                self.assertEqual(c.post('/ui/v1/sessions',json={'request_id':'hit','cache_mode':'miss'}).status_code,409)
                self.assertEqual(c.get('/ui/v1/sessions/'+sid).json()['cache_mode'],'hit')
                c.post('/ui/v1/sessions/'+sid+'/finish',json={'request_id':'end-hit'})
                miss=c.post('/ui/v1/sessions',json={'request_id':'miss','cache_mode':'miss'}).json()
                b=self.answer(c,miss['session_id'],'miss-turn');self.assertEqual(b['answer_source'],'MODEL')
                self.assertEqual(b['actual_backend'],'CPU_REFERENCE');self.assertTrue(b['delivery_receipt']['model_called']);self.assertEqual(self.cpu.count,1)
    def test_mode_switch_preserves_cache_and_old_turn_mode(self):
        factories={'native':dict(label='CPU',factory=lambda:self.engine(self.cpu,self.cache)),
                   'managed-pl':dict(label='FPGA',factory=lambda:self.engine(self.fpga,None))}
        app=create_app(backend='native',engine_factory=factories['native']['factory'],backend_options=factories)
        with TestClient(app) as c:
            coordinator=app.state.coordinator;self.assertTrue(coordinator.initialized.wait(3))
            sid=c.post('/ui/v1/sessions',json={'request_id':'cpu','cache_mode':'hit'}).json()['session_id']
            self.answer(c,sid,'cpu-answer');c.post('/ui/v1/sessions/'+sid+'/finish',json={'request_id':'done'})
            c.post('/ui/v1/backend',json={'request_id':'switch','backend':'managed-pl'})
            end=time.monotonic()+3
            while not coordinator.status()['ready'] and time.monotonic()<end:time.sleep(.01)
            new=c.post('/ui/v1/sessions',json={'request_id':'fpga','cache_mode':'hit'}).json()['session_id']
            answer=self.answer(c,new,'fpga-answer')
            self.assertEqual(answer['answer_source'],'MODEL_CACHE');self.assertEqual(answer['execution_mode'],'FPGA');self.assertEqual(self.fpga.count,0)
            self.assertEqual(c.get('/ui/v1/sessions/'+sid+'/turns/cpu-answer').json()['execution_mode'],'CPU')

if __name__=='__main__':unittest.main()
