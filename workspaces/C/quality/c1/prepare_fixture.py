"""Create THREE synthetic evaluator examples. This never runs a model."""
from pathlib import Path
import json
from validate_c1 import load_frozen
from evaluate_c1 import answer_hash

ROOT=Path(__file__).resolve().parents[2]


def main():
    manifest,rows,*_=load_frozen()
    chosen=[next(r for r in rows if r['case_id']=='sp_chest_01' and r['category']==cat and r['must_cover_slots']==slots)
            for cat,slots in [('normal',['location']),('unknown',['ecg']),('normal',['onset'])]]
    predictions=[]; annotations=[]
    for index,r in enumerate(chosen):
        answer=r['reference_answer'] if index<2 else '我拒绝回答这个起病时间问题。'
        outcome=['generated','unknown','refusal'][index]
        predictions.append(dict(test_id=r['test_id'],run_id='C1_SYNTHETIC_EVALUATOR_EXAMPLE_NOT_MODEL_RUN',
            testset_sha256=manifest['testset_sha256'],case_sha256=r['case_sha256'],
            execution_kind='PC_FIXTURE',outcome=outcome,answer=answer,
            predicted_slots=r['must_cover_slots'] if index<2 else [],template_fallback=index==1,hardware_fallback=False))
        annotations.append(dict(test_id=r['test_id'],answer_sha256=answer_hash(answer),source='synthetic_fixture',
            fully_annotated=True,policy_pass=True,expected_behavior_satisfied=index<2,policy_violations=[],
            claims=[dict(fact_id='fact.location',start=0,end=len(answer),verdict='consistent')] if index==0 else []))
    output=ROOT/'bench/e2e/c1/fixtures'
    output.mkdir(parents=True,exist_ok=True)
    for name,records in [('predictions.synthetic.jsonl',predictions),('annotations.synthetic.jsonl',annotations)]:
        (output/name).write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in records)+'\n',encoding='utf-8')
    print('THREE PC_FIXTURE examples: known answer, unknown template, deliberate refusal failure. No model/teacher/board measurement.')


if __name__=='__main__':
    main()
