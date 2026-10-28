"""Twenty-case web selection, new histories and opening/score behavior (PC fixtures)."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
WEB=ROOT/'platform/qwen35/web'
sys.path.insert(0,str(WEB));sys.path.insert(0,str(WEB/'vendor/web_gateway/src'))
from patient_web.reference.domain import load_case,Transcript,CASE_IDS
from patient_web.reference.planning import plan
from patient_web.reference.checking import check
from patient_web.reference.session import Session
from patient_web.engine import TextEngine
from natural_patient_prompt import prompt_messages


class Tests(unittest.TestCase):
    def test_twenty_cases_have_titles_and_patient_openings(self):
        engine=TextEngine('demo')
        rows=engine.cases()
        self.assertEqual(len(rows),20)
        self.assertEqual([r['case_id'] for r in rows],list(CASE_IDS))
        for r in rows:
            self.assertTrue(r['title']);self.assertTrue(r['chief_complaint'])
            s=engine.new_session(r['case_id'])
            self.assertTrue(s.snapshot()['chief_complaint'])
            self.assertEqual(s.snapshot()['received'],[])
            self.assertEqual(s.recompute_score_for_host()['score'],0)

    def test_new_histories_keep_drug_and_time_scope(self):
        for cid,slot,question in [('SYN_CP_04','allergy','有什么药物过敏？'),
                                  ('SYN_CP_19','medications','今天用药了吗？'),
                                  ('SYN_CP_14','medications','平时服药吗？')]:
            case=load_case(cid)
            p=plan(case,Transcript('history',question,None,'typed',None,None),())
            self.assertEqual(p.required_fact_ids,(slot,))
            text=prompt_messages(p,question)[-1]['content'].split('\n',1)[1]
            self.assertEqual(check(p,text)['status'],'pass')
            self.assertIn(case.fact(slot).value,text)
            if slot=='medications':self.assertIn('今天' if cid.endswith('19') else '平时',text)

    def test_opening_does_not_change_first_question_score(self):
        class ModelFixture:
            def generate(self,messages,**kwargs):
                return dict(text=messages[-1]['content'].split('\n',1)[1],status='OK',eos=True)
        s=Session('SYN_CP_20',software_test=True,prompt_builder=prompt_messages)
        r=s.submit(dict(request_id='location',text='你具体是哪儿疼？',source='typed',final=True),ModelFixture())
        self.assertEqual(r['answer_source'],'MODEL')
        s.trusted_delivery('location',0,kind='PC_TEXT_TEST_ACK')
        self.assertEqual(s.recompute_score_for_host()['score'],10)

if __name__=='__main__':unittest.main()
