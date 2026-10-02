from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import sys
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from validate_c1 import load_frozen, read_jsonl, normalize, validate_records, leakage_audit
from evaluate_c1 import evaluate, score_mae, answer_hash
from review_c1 import compare


class C1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest,cls.test,cls.dev,cls.cases,cls.rubric,cls.audit=load_frozen()

    def prediction(self,row,answer='胸口中间',outcome='generated',slots=None):
        return dict(test_id=row['test_id'],answer=answer,outcome=outcome,predicted_slots=row['must_cover_slots'] if slots is None else slots,
            testset_sha256=self.manifest['testset_sha256'],case_sha256=row['case_sha256'],run_id='synthetic-unit-test',
            execution_kind='PC_FIXTURE',hardware_fallback=False,template_fallback=outcome=='template_fallback')

    def annotation(self,pred,fact_id='fact.location',verdict='consistent'):
        return dict(test_id=pred['test_id'],answer_sha256=answer_hash(pred['answer']),source='synthetic_fixture',fully_annotated=True,
            policy_pass=True,expected_behavior_satisfied=True,policy_violations=[],
            claims=[] if fact_id is None else [dict(fact_id=fact_id,start=0,end=len(pred['answer']),verdict=verdict)])

    def location(self):
        return next(r for r in self.test if r['category']=='normal' and r['must_cover_slots']==['location'])

    def test_counts_unique_questions_all_cases_and_categories(self):
        self.assertEqual(len(self.test),324)
        self.assertEqual(len({normalize(r['input']['text']) for r in self.test}),324)
        self.assertEqual(len(self.dev),54)
        for c in self.cases:
            rows=[r for r in self.test if r['case_id']==c['case_id']]
            self.assertEqual(len(rows),108)
            self.assertEqual(len({r['category'] for r in rows}),10)

    def test_sources_templates_and_near_duplicates_separate(self):
        self.assertEqual(self.audit['near_duplicate_pairs'],[])
        self.assertEqual(self.audit['shared_source_files'],[])
        self.assertEqual(self.audit['shared_family_ids'],[])
        self.assertLess(self.audit['max_cross_split_similarity'],.80)
        self.assertEqual(self.audit['distinct_dev_inputs'],18)

    def test_shared_source_or_near_copy_rejected(self):
        dev=deepcopy(self.dev)
        dev[0]['provenance']['source_file']=self.test[0]['provenance']['source_file']
        with self.assertRaises(ValueError): leakage_audit(self.test,dev)
        dev=deepcopy(self.dev)
        dev[0]['input']['text']=self.test[0]['input']['text']+'请回答'
        self.assertTrue(leakage_audit(self.test,dev)['near_duplicate_pairs'])

    def test_duplicate_normalized_test_question_rejected(self):
        rows=deepcopy(self.test)
        rows[1]['input']['text']=rows[0]['input']['text']
        with self.assertRaises(ValueError): validate_records(rows,self.dev,self.cases,self.rubric)

    def test_case_hash_or_fact_partition_change_rejected(self):
        for key,value in [('case_sha256','0'*64),('forbidden_fact_ids',[])]:
            rows=deepcopy(self.test); rows[0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): validate_records(rows,self.dev,self.cases,self.rubric)

    def test_frozen_byte_edit_detected_in_temporary_copy(self):
        with tempfile.TemporaryDirectory(prefix='c1-freeze-') as tmp:
            copy=Path(tmp)/'frozen'; shutil.copytree(HERE/'frozen',copy)
            with (copy/'test_set.engineering_v1.jsonl').open('ab') as f: f.write(b'\n')
            with self.assertRaises(ValueError): load_frozen(copy)

    def test_metadata_never_claims_medical_review(self):
        for row in self.test+self.dev:
            self.assertEqual(row['review']['status'],'ENGINEERING_DRAFT')
            self.assertIsNone(row['review']['reviewer'])
            self.assertFalse(row['provenance']['clinical_independence_claim'])

    def test_factual_consistency_and_coverage_both_reported(self):
        rows=[self.location(),deepcopy(self.location())]
        rows[1]['test_id']='another-test'
        p=self.prediction(rows[0]); a=self.annotation(p)
        result=evaluate(rows,[p],[a],self.manifest['testset_sha256'])
        self.assertEqual(result['factuality']['conditional_consistency_rate'],1)
        self.assertEqual(result['factuality']['consistent_factual_coverage'],.5)
        self.assertEqual(result['missing_prediction_count'],1)
        self.assertEqual(result['slots']['micro_recall'],.5)
        self.assertEqual(result['status'],'FIXTURE_ONLY')

    def test_all_refusals_cannot_inflate_success_or_f1(self):
        row=self.location(); p=self.prediction(row,'拒绝回答','refusal',[]); a=self.annotation(p,None)
        a['expected_behavior_satisfied']=False
        result=evaluate([row],[p],[a],self.manifest['testset_sha256'])
        self.assertIsNone(result['factuality']['conditional_consistency_rate'])
        self.assertEqual(result['factuality']['factual_answer_coverage'],0)
        self.assertEqual(result['factuality']['complete_expected_response_coverage'],0)
        self.assertEqual(result['slots']['micro_f1'],0)
        self.assertEqual(result['failures']['refusal_when_known'],1)

    def test_correct_unknown_completion_not_counted_as_factual(self):
        row=next(r for r in self.test if r['category']=='unknown')
        p=self.prediction(row,'设定没有提供，我不清楚','unknown'); a=self.annotation(p,None)
        result=evaluate([row],[p],[a],self.manifest['testset_sha256'])
        self.assertEqual(result['factuality']['complete_expected_response_coverage'],1)
        self.assertEqual(result['factuality']['factual_answers'],0)
        self.assertIsNone(result['factuality']['conditional_consistency_rate'])

    def test_invented_unknown_normal_result_is_unsupported(self):
        row=next(r for r in self.test if r['category']=='unknown' and r['must_cover_slots']==['ecg'])
        p=self.prediction(row,'心电图正常','generated'); a=self.annotation(p,'unknown.ecg')
        result=evaluate([row],[p],[a],self.manifest['testset_sha256'])
        self.assertEqual(result['failures']['unsupported_fact'],1)
        self.assertEqual(result['factuality']['conditional_consistency_rate'],0)

    def test_unasked_true_fact_is_forbidden_disclosure(self):
        row=self.location(); p=self.prediction(row,'年龄五十二岁'); a=self.annotation(p,'fact.identity')
        result=evaluate([row],[p],[a],self.manifest['testset_sha256'])
        self.assertEqual(result['failures']['forbidden_disclosure'],1)
        self.assertEqual(result['factuality']['complete_expected_response_coverage'],0)

    def test_missing_answer_annotation_is_not_assumed_nonfactual(self):
        row=self.location(); p=self.prediction(row)
        result=evaluate([row],[p],[],self.manifest['testset_sha256'])
        self.assertIsNone(result['factuality']['conditional_consistency_rate'])
        self.assertEqual(result['factuality']['unannotated_answers'],1)
        self.assertEqual(result['failures']['unannotated_answer'],1)
        self.assertIsNone(result['factuality']['factual_answer_coverage'])
        self.assertIsNone(result['factuality']['consistent_factual_coverage'])

    def test_multi_slot_recognition_without_all_answer_facts_is_incomplete(self):
        row=next(r for r in self.test if r['category']=='multi_slot' and r['must_cover_slots']==['location','radiation'])
        p=self.prediction(row); a=self.annotation(p)
        result=evaluate([row],[p],[a],self.manifest['testset_sha256'])
        self.assertEqual(result['slots']['micro_f1'],1)
        self.assertEqual(result['factuality']['complete_expected_response_coverage'],0)
        self.assertEqual(result['failures']['unexpected_behavior'],1)

    def test_answer_annotations_do_not_award_coverage_for_unreviewed_predictions(self):
        row=self.location(); second=deepcopy(row); second['test_id']='unreviewed'
        p1=self.prediction(row); p2=self.prediction(second); a1=self.annotation(p1)
        result=evaluate([row,second],[p1,p2],[a1],self.manifest['testset_sha256'])
        self.assertIsNone(result['factuality']['conditional_consistency_rate'])
        self.assertIsNone(result['factuality']['factual_answer_coverage'])
        self.assertEqual(result['factuality']['observed_factual_coverage_lower_bound'],.5)

    def test_annotation_cannot_follow_changed_answer(self):
        row=self.location(); p=self.prediction(row); a=self.annotation(p)
        p['answer']='我在说另一件事情'
        with self.assertRaises(ValueError): evaluate([row],[p],[a],self.manifest['testset_sha256'])

    def test_llm_self_annotation_and_fixture_on_real_run_rejected(self):
        row=self.location(); p=self.prediction(row); a=self.annotation(p)
        a['source']='llm_self_review'
        with self.assertRaises(ValueError): evaluate([row],[p],[a],self.manifest['testset_sha256'])
        a=self.annotation(p); p['execution_kind']='KV260_REAL'
        with self.assertRaises(ValueError): evaluate([row],[p],[a],self.manifest['testset_sha256'])

    def test_claim_span_and_policy_contradiction_rejected(self):
        row=self.location(); p=self.prediction(row); a=self.annotation(p)
        a['claims'][0]['end']=999
        with self.assertRaises(ValueError): evaluate([row],[p],[a],self.manifest['testset_sha256'])
        a=self.annotation(p); a['policy_violations']=['score_tampering']
        with self.assertRaises(ValueError): evaluate([row],[p],[a],self.manifest['testset_sha256'])

    def test_fallback_mechanisms_are_separate_from_unknown_outcome(self):
        row=next(r for r in self.test if r['category']=='unknown')
        p=self.prediction(row,'我不知道','unknown'); p['template_fallback']=True
        a=self.annotation(p,None)
        result=evaluate([row],[p],[a],self.manifest['testset_sha256'])
        self.assertEqual(result['rates']['template_fallback'],1)
        self.assertEqual(result['rates']['hardware_fallback'],0)
        self.assertEqual(result['rates']['unknown'],1)

    def test_error_timeout_and_unexpected_slots_remain_failures(self):
        row=self.location(); p=self.prediction(row,'','timeout',['unexpected'])
        result=evaluate([row],[p],[],self.manifest['testset_sha256'])
        self.assertEqual(result['rates']['timeout'],1)
        self.assertEqual(result['slots']['fp'],1)
        self.assertEqual(result['slots']['fn'],1)
        self.assertEqual(result['rates']['completion'],0)

    def test_prediction_duplicate_unknown_id_or_dataset_mismatch_rejected(self):
        row=self.location(); p=self.prediction(row)
        with self.assertRaises(ValueError): evaluate([row],[p,p],[],self.manifest['testset_sha256'])
        for field in ['test_id','case_sha256','testset_sha256']:
            bad=deepcopy(p); bad[field]='wrong'
            with self.subTest(field=field),self.assertRaises(ValueError): evaluate([row],[bad],[],self.manifest['testset_sha256'])

    def test_no_teacher_ratings_means_na_not_zero_mae(self):
        result=score_mae([],[])
        self.assertEqual(result['status'],'NOT_TESTED')
        self.assertIsNone(result['mae'])
        self.assertEqual(result['mae_by_rater'],{})

    def test_teacher_mae_preserves_each_rater_and_disagreement(self):
        p=[dict(session_id='synthetic-session',total_score=70,score_source='deterministic_rules',transcript_sha256='hash')]
        ratings=[dict(session_id='synthetic-session',total_score=s,transcript_sha256='hash',status='REVIEWED',source='human_teacher',
            reviewer_id=r,qualification_reference='UNIT_TEST_ONLY_NOT_A_REAL_TEACHER',review_reference='SYNTHETIC_FIXTURE') for r,s in [('fixture-rater-1',60),('fixture-rater-2',90)]]
        result=score_mae(p,ratings)
        self.assertEqual(result['mae_by_rater']['fixture-rater-1']['mae'],10)
        self.assertEqual(result['mae_by_rater']['fixture-rater-2']['mae'],20)
        self.assertEqual(len(result['disagreements']),1)
        self.assertFalse(result['averaging_reference_scores'])
        self.assertIsNone(result['mae'])

    def test_fake_teacher_missing_reference_or_other_transcript_rejected(self):
        t=dict(session_id='s',total_score=80,status='REVIEWED',source='human_teacher',reviewer_id='fixture',
            qualification_reference='UNIT_TEST_ONLY',review_reference='UNIT_TEST_ONLY',transcript_sha256='other')
        p=[dict(session_id='s',total_score=80,score_source='deterministic_rules',transcript_sha256='original')]
        with self.assertRaises(ValueError): score_mae(p,[t])
        t.pop('qualification_reference')
        with self.assertRaises(ValueError): score_mae([], [t])

    def test_review_packets_have_72_questions_6_sessions_and_no_gold_hints(self):
        for slot in ['reviewer_1','reviewer_2']:
            forms=read_jsonl(HERE/f'review/{slot}_questions.template.jsonl')
            scores=read_jsonl(HERE/f'review/{slot}_sessions.template.jsonl')
            self.assertEqual(len(forms),72); self.assertEqual(len(scores),6)
            for f in forms:
                self.assertIsNone(f['reference_answer']); self.assertIsNone(f['reviewer_id'])
                self.assertEqual(f['status'],'PENDING')
                self.assertIsNone(f['must_cover_slots'])

    def test_pending_reviews_do_not_claim_approval(self):
        a=read_jsonl(HERE/'review/reviewer_1_questions.template.jsonl')
        b=read_jsonl(HERE/'review/reviewer_2_questions.template.jsonl')
        result=compare(a,b,{r['test_id']:r for r in self.test},self.manifest['testset_sha256'])
        self.assertEqual(result['reviewed_counts'],[0,0]); self.assertEqual(result['pending_counts'],[72,72])
        self.assertFalse(result['medical_approval']); self.assertFalse(result['at_least_60_joint_independent_reviews'])

    def test_review_disagreements_saved_without_automatic_resolution(self):
        base=read_jsonl(HERE/'review/reviewer_1_questions.template.jsonl')[0]
        row=next(r for r in self.test if r['test_id']==base['test_id'])
        a=deepcopy(base); b=deepcopy(base)
        for f,rater in [(a,'fixture-human-1'),(b,'fixture-human-2')]:
            f.update(status='REVIEWED',reviewer_id=rater,qualification_reference='UNIT_TEST_NOT_REAL',review_reference='UNIT_TEST_NOT_REAL',reviewed_at='2026-10-01T12:00:00+08:00')
            for key in ['allowed_fact_ids','forbidden_fact_ids','allowed_unknown_ids','must_cover_slots','expected_behavior','reference_answer']: f[key]=row[key]
        b['reference_answer']='教师测试意见中的另一种表述（虚构）'
        result=compare([a],[b],{r['test_id']:r for r in self.test},self.manifest['testset_sha256'])
        self.assertEqual(len(result['disagreements']),1); self.assertIsNone(result['disagreements'][0]['resolution'])
        self.assertFalse(result['automatic_resolution'])
        b['reviewer_id']=a['reviewer_id']
        with self.assertRaises(ValueError): compare([a],[b],{r['test_id']:r for r in self.test},self.manifest['testset_sha256'])


if __name__=='__main__':
    unittest.main()
