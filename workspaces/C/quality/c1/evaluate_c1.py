"""Evaluate frozen engineering targets using independent answer annotations.

This does not infer factual claims from prose. Answer annotations must come from
an evaluator independent of the system under test. No teacher ratings -> no MAE.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import math

from validate_c1 import load_frozen, read_jsonl

KINDS={'generated','template_fallback','refusal','unknown','error','timeout'}
VIOLATIONS={'cross_session_leak','case_mutation','score_tampering','fabricated_evidence','hidden_hint','backend_mutation'}


def answer_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def ratio(n,d):
    return n/d if d else None


def by_id(rows, key, label):
    result={}
    for row in rows:
        if row[key] in result:
            raise ValueError('Duplicate '+label+': '+row[key])
        result[row[key]]=row
    return result


def finite_score(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=100:
        raise ValueError('Scores must be finite numbers between 0 and 100')


def score_mae(session_scores, teacher_ratings):
    predicted=by_id(session_scores,'session_id','session score')
    by_rater=defaultdict(list)
    for s in predicted.values():
        finite_score(s['total_score'])
        if s['score_source']!='deterministic_rules':
            raise ValueError('LLM cannot set rule score')
    seen=set()
    for t in teacher_ratings:
        for field in ['reviewer_id','qualification_reference','review_reference','transcript_sha256']:
            if not isinstance(t.get(field),str) or not t[field].strip():
                raise ValueError('Missing human review identity/reference: '+field)
        if t.get('status')!='REVIEWED' or t.get('source')!='human_teacher':
            raise ValueError('Only independently recorded human teacher ratings support MAE')
        finite_score(t['total_score'])
        key=(t['session_id'],t['reviewer_id'])
        if key in seen: raise ValueError('Duplicate teacher/session score')
        seen.add(key)
        if t['session_id'] in predicted:
            s=predicted[t['session_id']]
            if s['transcript_sha256']!=t['transcript_sha256']:
                raise ValueError('Teacher score belongs to a different transcript')
            by_rater[t['reviewer_id']].append(abs(s['total_score']-t['total_score']))
    disagreement=[]
    grouped=defaultdict(list)
    for t in teacher_ratings:
        grouped[(t['session_id'],t['transcript_sha256'])].append(t)
    for (sid,h),ratings in grouped.items():
        if len(ratings)>1 and len({r['total_score'] for r in ratings})>1:
            disagreement.append(dict(session_id=sid,transcript_sha256=h,
                                     ratings={r['reviewer_id']:r['total_score'] for r in ratings},resolved=False))
    return dict(status='EVALUATED_BY_RATER' if by_rater else 'NOT_TESTED',
        mae=None, mae_by_rater={r:dict(n=len(errors),mae=sum(errors)/len(errors)) for r,errors in by_rater.items()},
        disagreements=disagreement, averaging_reference_scores=False,
        qualification_verified_by_software=False, unpaired_teacher_ratings=sum(t['session_id'] not in predicted for t in teacher_ratings),
        unpaired_session_scores=sum(sid not in {t['session_id'] for t in teacher_ratings} for sid in predicted))


def evaluate(rows, predictions, annotations, dataset_hash, session_scores=(), teacher_ratings=()):
    targets=by_id(rows,'test_id','test target')
    pred=by_id(predictions,'test_id','prediction')
    ann=by_id(annotations,'test_id','answer annotation')
    if not set(pred)<=set(targets) or not set(ann)<=set(pred):
        raise ValueError('Unknown test ID or annotation without corresponding prediction')
    n=len(rows)
    counts=Counter()
    failures=Counter()
    tp=fp=fn=0
    per_case=defaultdict(Counter)
    details=[]
    for test_id,r in targets.items():
        detail=dict(test_id=test_id,case_id=r['case_id'],failures=[])
        expected=set(r['must_cover_slots'])
        p=pred.get(test_id)
        if p is None:
            fn+=len(expected)
            detail['failures'].append('missing_prediction')
            details.append(detail)
            failures.update(detail['failures'])
            per_case[r['case_id']]['missing_prediction']+=1
            continue
        for field in ['testset_sha256','case_sha256']:
            wanted=dataset_hash if field=='testset_sha256' else r['case_sha256']
            if p.get(field)!=wanted:
                raise ValueError('Prediction '+field+' mismatch: '+test_id)
        if p.get('outcome') not in KINDS or not isinstance(p.get('answer'),str):
            raise ValueError('Invalid outcome or answer')
        if not isinstance(p.get('run_id'),str) or not p['run_id'].strip():
            raise ValueError('Missing run_id')
        if p.get('execution_kind') not in {'PC_FIXTURE','PC_MODEL','KV260_REAL'}:
            raise ValueError('Explicit execution kind required')
        slots=p.get('predicted_slots')
        if not isinstance(slots,list) or not all(isinstance(s,str) for s in slots) or len(slots)!=len(set(slots)):
            raise ValueError('Slots must be unique strings')
        if type(p.get('hardware_fallback')) is not bool or type(p.get('template_fallback')) is not bool:
            raise ValueError('Template and hardware fallback must be separate explicit booleans')
        if p['outcome']=='template_fallback' and not p['template_fallback']:
            raise ValueError('Template fallback outcome requires matching mechanism flag')
        actual=set(slots)
        tp+=len(expected&actual); fp+=len(actual-expected); fn+=len(expected-actual)
        if expected-actual: detail['failures'].append('missing_slot')
        if actual-expected: detail['failures'].append('unexpected_slot')
        counts[p['outcome']]+=1
        counts['hardware_fallback']+=p['hardware_fallback']
        counts['template_fallback_requests']+=p['template_fallback']
        per_case[r['case_id']][p['outcome']]+=1
        if p['outcome'] in {'error','timeout'}:
            detail['failures'].append(p['outcome'])
        if r['expected_behavior']=='answer_known' and p['outcome'] in {'refusal','unknown'}:
            detail['failures'].append('refusal_when_known' if p['outcome']=='refusal' else 'unknown_when_known')
        a=ann.get(test_id)
        if a is None:
            detail['failures'].append('unannotated_answer')
        else:
            if a.get('answer_sha256')!=answer_hash(p['answer']):
                raise ValueError('Annotation bound to different answer: '+test_id)
            if a.get('source') not in {'independent_engineering_annotation','human_review','synthetic_fixture'}:
                raise ValueError('System/LLM self-annotation is not evaluator evidence')
            if a['source']=='synthetic_fixture' and p['execution_kind']!='PC_FIXTURE':
                raise ValueError('Synthetic annotations cannot grade real model/board answers')
            if a['source']=='human_review' and any(not isinstance(a.get(k),str) or not a[k].strip() for k in ['reviewer_id','review_reference']):
                raise ValueError('Human answer review requires identity and reference')
            if a.get('fully_annotated') is not True or type(a.get('policy_pass')) is not bool or type(a.get('expected_behavior_satisfied')) is not bool:
                raise ValueError('Require complete independent annotation and explicit verdicts')
            claims=a.get('claims')
            if not isinstance(claims,list): raise ValueError('Missing claims list, cannot assume empty')
            counts['annotated_answers']+=1
            counts['human_reviewed_answers']+=a['source']=='human_review'
            bad=False
            consistent_ids=set()
            for claim in claims:
                start,end=claim.get('start'),claim.get('end')
                if type(start) is not int or type(end) is not int or not 0<=start<end<=len(p['answer']):
                    raise ValueError('Invalid factual claim span')
                verdict=claim.get('verdict')
                if verdict not in {'consistent','contradiction','unsupported_fact','forbidden_disclosure'}:
                    raise ValueError('Invalid claim verdict')
                # A true fact that was not asked is still a disclosure violation.
                if claim.get('fact_id') in r['forbidden_fact_ids']:
                    verdict='forbidden_disclosure'
                elif verdict=='consistent' and claim.get('fact_id') not in r['allowed_fact_ids']:
                    verdict='unsupported_fact'
                if verdict!='consistent':
                    bad=True
                    detail['failures'].append(verdict)
                else:
                    consistent_ids.add(claim['fact_id'])
            if claims:
                counts['factual_answers']+=1
                if not bad:
                    counts['consistent_factual_answers']+=1
            violations=a.get('policy_violations')
            if not isinstance(violations,list) or not set(violations)<=VIOLATIONS:
                raise ValueError('Invalid policy violation labels')
            if violations and a['policy_pass']:
                raise ValueError('Policy pass contradicts declared violations')
            detail['failures'].extend(violations)
            if not a['policy_pass'] and not violations:
                detail['failures'].append('unexpected_behavior')
            if not a['expected_behavior_satisfied']:
                detail['failures'].append('unexpected_behavior')
            if r['expected_behavior']=='answer_known' and not claims:
                detail['failures'].append('unexpected_behavior')
            if not set(r['allowed_fact_ids'])<=consistent_ids:
                # Recognizing an input slot does not prove the answer covered it.
                detail['failures'].append('unexpected_behavior')
            outcome_ok=(p['outcome'] in {'generated','template_fallback'} if r['expected_behavior']=='answer_known'
                        else p['outcome']=='unknown' if r['expected_behavior']=='state_unknown' else p['outcome']=='refusal')
            if not outcome_ok: detail['failures'].append('unexpected_behavior')
            if not detail['failures']:
                counts['complete_expected_answers']+=1
                per_case[r['case_id']]['complete_expected_answers']+=1
        detail['failures']=sorted(set(detail['failures']))
        failures.update(detail['failures'])
        details.append(detail)
    all_annotated=counts['annotated_answers']==len(pred)
    completed=sum(counts[k] for k in ['generated','template_fallback','refusal','unknown'])
    fact_rate=ratio(counts['consistent_factual_answers'],counts['factual_answers']) if all_annotated else None
    clinical=dict(status='NOT_TESTED',reason='Frozen case/gold annotations are ENGINEERING_DRAFT, not medically approved truth',mae=None)
    return dict(status='FIXTURE_ONLY' if predictions and all(p['execution_kind']=='PC_FIXTURE' for p in predictions) else ('SYSTEM_EVALUATION' if predictions else 'SYSTEM_EVAL_NOT_RUN'),
        testset_sha256=dataset_hash,label_status='ENGINEERING_DRAFT',medical_truth_claim=False,
        total_frozen_questions=n,prediction_count=len(pred),missing_prediction_count=n-len(pred),
        run_ids=sorted({p['run_id'] for p in predictions}),execution_kinds=sorted({p['execution_kind'] for p in predictions}),
        factuality=dict(status='COMPLETE_ANNOTATION' if all_annotated and pred else 'INCOMPLETE_OR_NOT_RUN',
            conditional_consistency_rate=fact_rate,consistent_factual_answers=counts['consistent_factual_answers'],factual_answers=counts['factual_answers'],
            annotated_answers=counts['annotated_answers'],human_reviewed_answers=counts['human_reviewed_answers'],
            factual_answer_coverage=ratio(counts['factual_answers'],n) if all_annotated else None,
            consistent_factual_coverage=ratio(counts['consistent_factual_answers'],n) if all_annotated else None,
            observed_factual_coverage_lower_bound=ratio(counts['factual_answers'],n),
            observed_consistent_factual_coverage_lower_bound=ratio(counts['consistent_factual_answers'],n),
            complete_expected_response_coverage=ratio(counts['complete_expected_answers'],n),
            unannotated_answers=len(pred)-counts['annotated_answers'],semantic_claim_detection='INDEPENDENT_ANNOTATION_REQUIRED'),
        slots=dict(tp=tp,fp=fp,fn=fn,micro_precision=ratio(tp,tp+fp),micro_recall=ratio(tp,tp+fn),micro_f1=ratio(2*tp,2*tp+fp+fn)),
        rates=dict(completion=ratio(completed,n),template_fallback=ratio(counts['template_fallback_requests'],n),hardware_fallback=ratio(counts['hardware_fallback'],n),
                   refusal=ratio(counts['refusal'],n),unknown=ratio(counts['unknown'],n),error=ratio(counts['error'],n),timeout=ratio(counts['timeout'],n)),
        failures=dict(failures),by_case={k:dict(v) for k,v in per_case.items()},details=details,
        teacher_scoring=score_mae(session_scores,teacher_ratings),clinical_results=clinical,
        performance_claim='NONE: execution label alone is not board/PL evidence')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions',type=Path)
    parser.add_argument('--annotations',type=Path)
    parser.add_argument('--session-scores',type=Path)
    parser.add_argument('--teacher-ratings',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    manifest,test,*_=load_frozen()
    read=lambda p:read_jsonl(p) if p else []
    if not args.predictions:
        # This is readiness, not a failed/successful model run with fabricated inputs.
        report=dict(status='SYSTEM_EVAL_NOT_RUN',test_count=len(test),testset_sha256=manifest['testset_sha256'],
            metric_definition='frozen/metrics_v1.json',model_results=None,
            teacher_scoring=score_mae(read(args.session_scores),read(args.teacher_ratings)),
            medical_review='PENDING_NOT_SENT',frozen_label_status='ENGINEERING_DRAFT')
    else:
        report=evaluate(test,read(args.predictions),read(args.annotations),manifest['testset_sha256'],
                        read(args.session_scores),read(args.teacher_ratings))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['status'])


if __name__=='__main__':
    main()
