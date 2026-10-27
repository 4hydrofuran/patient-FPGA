"""Check every measured window against unchanged original facts/checker and v1 answers."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'vendor/web_gateway/src'))
from patient_web.reference.domain import load_case,Transcript
from patient_web.reference.planning import plan
from patient_web.reference.checking import check


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def stats(values):return dict(min_ms=min(values),median_ms=statistics.median(values),max_ms=max(values),samples=len(values))


def compare(root,output,equivalent_severity_form=False):
    baseline=read(root/'baseline-browser/RESULT.json');assert baseline['mode']=='realtime'
    windows=read(root/'WINDOWS.json')['rows'];original={r['id']:r for r in baseline['rows']}
    assert len(original)==25
    rows=[];summaries=[]
    for window in windows:
        label=window['window'];result=read(root/(label+'-browser')/'RESULT.json')
        service=read(root/(label+'-serve')/'RESULT.json')
        assert result['mode']=='realtime' and len(result['rows'])==25
        assert service['native_count']==25 and service['cache'] is None and service['worker_exit']==0
        for item in result['rows']:
            old=original[item['id']]
            for key in ('case_id','question'):assert item[key]==old[key],(label,item['id'],key)
            turn=item['turn'];spec=turn['timing']['native_speculative_decoding']
            assert turn['answer_source']=='MODEL' and turn['actual_backend']=='CPU_REFERENCE'
            assert turn['delivery_receipt']['model_called'] is True and turn['delivery_receipt']['validation_status']=='pass'
            assert spec['answer_cache_used'] is False and spec['forced_output'] is False
            assert spec['target_eos_verified'] or spec['fallback_full_prompt_replayed']
            assert item['measured_with']=='REAL_EDGE_REAL_HTTP_SSE' and item['timing']['visibility_state']=='visible'
            p=plan(load_case(item['case_id']),Transcript.parse(dict(request_id=item['id'],text=item['question'],source='typed',final=True)),())
            same_text=item['answer']==old['answer']
            if not same_text:assert equivalent_severity_form and any(f.slot=='severity' for f in p.facts)
            checked=check(p,item['answer'])
            assert checked['status']=='pass' and set(checked['covered_fact_ids'])==set(p.required_fact_ids)
            prefix=turn['timing']['native_prefix_cache'];assert prefix['hit'] is True
            selected_severity=label!='baseline' and 'severity' in [f.slot for f in p.facts] and len(p.facts)==1
            assert prefix['reused_tokens'] in ((37,38,43) if selected_severity else (34,))
            before=old['timing']['submit_to_paint_ms'];after=item['timing']['submit_to_paint_ms']
            rows.append(dict(window=label,id=item['id'],case_id=item['case_id'],question=item['question'],
                v1_ms=before,v2_ms=after,reduction_ms=before-after,reused_tokens=prefix['reused_tokens'],
                full_original_check=True,same_text=same_text,target_eos_verified=spec['target_eos_verified']))
        values=[r['v2_ms'] for r in rows if r['window']==label]
        summaries.append(dict(window=label,under_1000=sum(v<1000 for v in values),**stats(values),
            startup_ready_s=read(root/(label+'-serve')/'HTTP_READY.json')['startup_ready_s']))
    candidates=[r for r in rows if r['window']!='baseline'];assert len(candidates)==75
    report=dict(status='PASS_75_OF_75_REAL_MODEL_BELOW_1S' if all(r['v2_ms']<1000 for r in candidates) else 'TARGET_NOT_MET',
        measurement='browser submit to complete checked answer DOM plus two animation frames',
        windows=summaries,candidate=stats([r['v2_ms'] for r in candidates]),under_1000=sum(r['v2_ms']<1000 for r in candidates),
        actual_model_calls=100,answer_cache_hits=0,byte_identical_to_v1=sum(r['same_text'] for r in rows),original_checker_pass=100,
        equivalent_severity_form_explicitly_selected=equivalent_severity_form,
        tail_rows=[r for r in candidates if r['id'] in ('DEV-005','V04')],rows=rows,BOARD='NOT_TESTED')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with output.with_suffix('.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','tail_rows')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--windows-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--equivalent-severity-form',action='store_true')
    a=p.parse_args();compare(a.windows_root,a.output,a.equivalent_severity_form)
