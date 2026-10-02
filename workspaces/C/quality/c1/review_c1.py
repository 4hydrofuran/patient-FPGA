"""Validate two independent rater overlays; preserve disagreements, never resolve."""
from pathlib import Path
from datetime import datetime
import argparse
import json

from validate_c1 import load_frozen, read_jsonl

FIELDS=['allowed_fact_ids','forbidden_fact_ids','allowed_unknown_ids','must_cover_slots','expected_behavior','reference_answer']


def checked_reviews(forms, targets, testset_hash):
    result={}
    reviewers=set()
    pending=0
    for f in forms:
        tid=f['test_id']
        if tid in result: raise ValueError('Duplicate rater question')
        if tid not in targets: raise ValueError('Unknown review target')
        target=targets[tid]
        if f['testset_sha256']!=testset_hash or f['case_sha256']!=target['case_sha256'] or f['input']!=target['input'] or f['case_id']!=target['case_id'] or f['case_version']!=target['case_version']:
            raise ValueError('Rater changed frozen input/case reference')
        if f['status']=='PENDING':
            pending+=1
            result[tid]=None
            continue
        if f['status'] not in {'REVIEWED','NEEDS_REVISION'}: raise ValueError('Unsupported review status')
        for k in ['reviewer_id','qualification_reference','reviewed_at','review_reference']:
            if not isinstance(f.get(k),str) or not f[k].strip():
                raise ValueError('Missing human review identity/qualification/reference')
        stamp=datetime.fromisoformat(f['reviewed_at'].replace('Z','+00:00'))
        if stamp.utcoffset() is None: raise ValueError('Review date needs timezone')
        for k in FIELDS[:4]:
            if not isinstance(f.get(k),list) or not all(isinstance(x,str) for x in f[k]) or len(f[k])!=len(set(f[k])):
                raise ValueError('Human labels require unique string lists')
        if f['expected_behavior'] not in {'answer_known','state_unknown','refuse_control'} or not isinstance(f['reference_answer'],str) or not f['reference_answer'].strip():
            raise ValueError('Incomplete human target annotation')
        if set(f['allowed_fact_ids']) & set(f['forbidden_fact_ids']): raise ValueError('Human allowed/forbidden overlap')
        known=set(target['allowed_fact_ids'])|set(target['forbidden_fact_ids'])
        if not set(f['allowed_fact_ids']+f['forbidden_fact_ids'])<=known:
            raise ValueError('Teacher requested new case facts: version the case, do not mutate v1')
        reviewers.add(f['reviewer_id'])
        result[tid]=f
    if len(reviewers)>1: raise ValueError('One rater file must contain one reviewer identity')
    return result,reviewers,pending


def compare(first, second, targets, testset_hash):
    a,ids1,pending1=checked_reviews(first,targets,testset_hash)
    b,ids2,pending2=checked_reviews(second,targets,testset_hash)
    if ids1 & ids2: raise ValueError('Independent review requires distinct human reviewer IDs')
    reviewed1={k for k,v in a.items() if v is not None}
    reviewed2={k for k,v in b.items() if v is not None}
    shared=reviewed1&reviewed2
    diffs=[]
    for tid in sorted(shared):
        fields={}
        for k in FIELDS:
            x,y=a[tid][k],b[tid][k]
            same=sorted(x)==sorted(y) if isinstance(x,list) else x==y
            if not same: fields[k]=dict(reviewer_1=x,reviewer_2=y)
        if fields or a[tid]['status']=='NEEDS_REVISION' or b[tid]['status']=='NEEDS_REVISION':
            diffs.append(dict(test_id=tid,fields=fields,reviewer_1_status=a[tid]['status'],reviewer_2_status=b[tid]['status'],resolution=None))
    return dict(status='REQUIRES_HUMAN_ADJUDICATION' if shared else 'PENDING_HUMAN_REVIEWS',
        reviewed_counts=[len(reviewed1),len(reviewed2)],pending_counts=[pending1,pending2],jointly_reviewed=len(shared),
        at_least_60_joint_independent_reviews=len(shared)>=60 and bool(ids1) and bool(ids2),
        distinct_reviewer_ids=[sorted(ids1),sorted(ids2)],disagreements=diffs,
        agreement_count=len(shared)-len(diffs),automatic_resolution=False,medical_approval=False,
        qualification_verified_by_software=False,release_gate='Human course/case/rubric approval and provenance still required')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewer-1',type=Path,required=True)
    parser.add_argument('--reviewer-2',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    manifest,test,*_=load_frozen()
    report=compare(read_jsonl(args.reviewer_1),read_jsonl(args.reviewer_2),{r['test_id']:r for r in test},manifest['testset_sha256'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['status'])
