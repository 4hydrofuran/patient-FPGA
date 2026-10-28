"""Requested random-case API and session continuity, PC fixtures only."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
WEB=ROOT/'platform/qwen35/web'
SOURCE=WEB/'integrated/B_601e69ca_A_case20_random_20261027/web_gateway/src'
sys.path.insert(0,str(WEB));sys.path.insert(0,str(SOURCE))
from fastapi.testclient import TestClient
from patient_web.api import create_app
from continuous_sessions import install


class Tests(unittest.TestCase):
    def test_draw_retry_refresh_finish_and_next_draw(self):
        app=create_app(backend='demo');coordinator=app.state.coordinator
        with tempfile.TemporaryDirectory() as d:
            install(coordinator,Path(d))
            with TestClient(app) as client,patch('patient_web.manager.secrets.choice',side_effect=['SYN_CP_20','SYN_CP_04']) as draw:
                self.assertTrue(coordinator.initialized.wait(3))
                first=client.post('/ui/v1/sessions',json={'request_id':'first'})
                self.assertEqual(first.status_code,201,first.text)
                a=first.json();self.assertEqual(a['case_id'],'SYN_CP_20')
                again=client.post('/ui/v1/sessions',json={'request_id':'first'}).json()
                self.assertEqual(again['session_id'],a['session_id']);self.assertTrue(again['replayed'])
                snapshot=client.get('/ui/v1/sessions/'+a['session_id']).json()
                self.assertEqual(snapshot['case_id'],'SYN_CP_20');self.assertTrue(snapshot['chief_complaint'])
                self.assertEqual(draw.call_count,1)
                client.post('/ui/v1/sessions/'+a['session_id']+'/finish',json={'request_id':'end'})
                self.assertEqual(client.get('/ui/v1/sessions/'+a['session_id']+'/evaluation').json()['rule_score']['score'],0)
                b=client.post('/ui/v1/sessions',json={'request_id':'next'}).json()
                self.assertEqual(b['case_id'],'SYN_CP_04');self.assertNotEqual(b['session_id'],a['session_id'])
                self.assertEqual(len(draw.call_args.args[0]),20)

    def test_student_cannot_choose_and_page_has_no_picker(self):
        app=create_app(backend='demo')
        with TestClient(app) as client:
            self.assertTrue(app.state.coordinator.initialized.wait(3))
            self.assertEqual(client.post('/ui/v1/sessions',json={'request_id':'pick','case_id':'SYN_CP_01'}).status_code,400)
            self.assertEqual(client.get('/ui/v1/cases').json(),{'selection':'random','case_count':20})
            html=client.get('/').text
            self.assertNotIn('id="cases"',html)
            self.assertIn('随机抽取并开始',html)

if __name__=='__main__':unittest.main()
