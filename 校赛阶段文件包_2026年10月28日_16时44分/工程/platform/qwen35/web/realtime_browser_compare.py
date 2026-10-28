"""Compare complete real browser answers with a fresh model call on both sides."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys


def stats(values):
    return dict(min=min(values), median=statistics.median(values), max=max(values), samples=len(values))


def compare(baseline, candidate, output, equivalent_forms=False):
    if equivalent_forms:
        here=Path(__file__).resolve().parent
        sys.path.insert(0,str(here/'vendor/web_gateway/src'))
        from patient_web.reference.domain import load_case,Transcript
        from patient_web.reference.planning import plan
        from patient_web.reference.checking import check
    read=lambda p:json.loads((Path(p)/'RESULT.json').read_text(encoding='utf-8'))
    a,b=read(baseline),read(candidate)
    assert a['mode']=='live' and b['mode']=='realtime'
    assert len(a['rows'])==len(b['rows']) and len(a['rows'])>=25
    rows=[]
    for old,new in zip(a['rows'],b['rows']):
        for key in ('id','case_id','question'):
            assert old[key]==new[key],(key,old,new)
        if equivalent_forms:
            p=plan(load_case(old['case_id']),Transcript.parse(dict(request_id=old['id'],text=old['question'],source='typed',final=True)),())
            for item in (old,new):
                checked=check(p,item['answer'])
                assert checked['status']=='pass' and set(checked['covered_fact_ids'])==set(p.required_fact_ids),(p,item,checked)
        else:assert old['answer']==new['answer'],(old,new)
        for item in (old,new):
            assert item['measured_with']=='REAL_EDGE_REAL_HTTP_SSE'
            turn=item['turn']
            assert turn['status']=='COMPLETED' and turn['answer_source']=='MODEL'
            assert turn['actual_backend']=='CPU_REFERENCE' and turn['delivery_receipt']['model_called'] is True
            assert turn['delivery_receipt']['validation_status']=='pass'
            assert item['timing']['visibility_state']=='visible'
        spec=new['turn']['timing']['native_speculative_decoding']
        assert spec['answer_cache_used'] is False and spec['forced_output'] is False
        assert spec['target_eos_verified'] or spec['fallback_full_prompt_replayed']
        before,after=old['timing']['submit_to_paint_ms'],new['timing']['submit_to_paint_ms']
        rows.append(dict(id=old['id'],serial_ms=before,realtime_ms=after,reduction_ms=before-after,
                         reduction_percent=(before-after)/before*100,draft_accepted=spec['accepted'],same_text=old['answer']==new['answer']))
    report=dict(status='PASS_REAL_BROWSER_REALTIME_MODEL_PAIRED_AB',rows=rows,total=len(rows),
                serial_ms=stats([r['serial_ms'] for r in rows]),realtime_ms=stats([r['realtime_ms'] for r in rows]),
                reduction_ms=stats([r['reduction_ms'] for r in rows]),
                within_1s=sum(r['realtime_ms']<=1000 for r in rows),
                draft_accepted=sum(r['draft_accepted'] for r in rows),answer_cache_hits=0,
                baseline_model_requests=len(rows),candidate_model_requests=len(rows),BOARD='NOT_TESTED')
    report.update(original_checker_equivalent_forms=equivalent_forms,wording_changed=sum(not r['same_text'] for r in rows))
    output=Path(output)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with output.with_suffix('.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return {k:v for k,v in report.items() if k!='rows'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--equivalent-forms',action='store_true',help='explicitly allow shorter original checker forms; both must cover all original facts')
    a=p.parse_args();print(json.dumps(compare(a.baseline,a.candidate,a.output,a.equivalent_forms),indent=2))
