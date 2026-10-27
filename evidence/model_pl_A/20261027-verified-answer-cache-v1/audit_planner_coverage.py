"""Prove catalog coverage through the actual planner, independently of the builder iterator."""
import itertools
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3];WEB=ROOT/'platform/qwen35/web';EV=Path(__file__).resolve().parent
sys.path.insert(0,str(WEB));sys.path.insert(0,str(WEB/'vendor/web_gateway/src'))
from verified_answer_cache import VerifiedAnswerCache,model_identity,file_sha
from patient_web.reference.domain import load_case,Transcript,SLOTS
from patient_web.reference.planning import plan,PATTERNS
from patient_web.reference.session import Session

questions=dict(location='疼痛在哪里？',quality='疼痛是什么感觉？',onset='胸痛什么时候开始？',duration='每次疼痛持续多久？',
    severity='疼痛程度如何？',radiation='疼痛会牵扯到别处吗？',trigger='疼痛诱因是什么？',relief='如何缓解疼痛？',
    dyspnea='是否气短？',allergy='是否过敏？',medications='是否用药？')
assert list(PATTERNS)==list(SLOTS)==list(questions)
parent=ROOT/'release/a12_fast_response_20261027_v2/short34-threads2'
prefix=json.loads((parent/'continuous/profile.json').read_text(encoding='utf-8'))['prefix_identity']
identity=model_identity(prefix,WEB/'vendor/web_gateway/src/patient_web/reference')
file=EV/'build01/catalog.json';cache=VerifiedAnswerCache(file,identity=identity,expected_sha256=file_sha(file))
rows=[]
for cid in ('SYN_CP_01','SYN_CP_02','SYN_CP_03'):
    case=load_case(cid)
    for n in (1,2):
        for slots in itertools.combinations(SLOTS,n):
            text='，'.join(questions[s].rstrip('？') for s in slots)+'？'
            p=plan(case,Transcript.parse(dict(request_id='coverage',text=text,source='typed',final=True)),())
            assert p.route=='answer' and tuple(p.required_fact_ids)==slots,(cid,slots,p.to_dict())
            assert cache.lookup(case,p) is not None,(cid,slots)
            rows.append(dict(case_id=cid,slots=list(slots),question=text,status='ACTUAL_PLANNER_AND_CACHE_PASS'))
class NeverModel:
    def generate(self,*a,**kw):raise AssertionError('context reuse invoked model')
s=Session('SYN_CP_01',software_test=True,answer_cache=cache)
for rid,text in [('location','疼痛在哪里？'),('duration','每次疼痛持续多久？'),('followup','那个呢？')]:
    response=s.submit(dict(request_id=rid,text=text,source='typed',final=True),NeverModel(),180)
    assert response['answer_source']=='MODEL_CACHE' and response['llm_calls']==0
    if rid=='followup':assert response['answer_plan']['reason']=='last_played_fact_explicit_followup'
    s.trusted_delivery(rid,s.epoch,kind='PC_TEXT_TEST_ACK')
assert s.recompute_score_for_host()['score']==20
report=dict(status='PASS_198_ACTUAL_PLANNER_QUESTIONS_AND_CONTEXT_FOLLOWUP',plans=len(rows),rows=rows,
    context_followup='MODEL_CACHE_NO_NEW_MODEL_CALL',score_after_followup=20,delivery_scope='PC_TEXT_TEST_ACK_FOR_CONTEXT_ONLY',
    original_checker_and_planner_preserved=True,BOARD='NOT_TESTED')
(EV/'PLANNER_COVERAGE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
