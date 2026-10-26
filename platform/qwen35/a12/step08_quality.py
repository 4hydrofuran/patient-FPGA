"""Evaluate every frozen dev item; keep raw failures and policy/model provenance."""
from collections import Counter
from dataclasses import asdict
import json
import re
import sys
from common import ROOT,save
from step08_common import OUT
sys.path.insert(0,str(ROOT))
from system_qwen35.app.domain import load_case,Transcript
from system_qwen35.app.planning import plan
from system_qwen35.app.checking import check,fallback

def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    audit=j(OUT/'GENERATION_AUDIT.json');assert audit['status']=='PASS_BOARD_ALL_FROZEN_DEV_PAIRED_GENERATION'
    frozen=j(OUT/'REQUESTS.json');model={r['id']:r for r in audit['cases']}
    policies={r['id']:r for r in frozen['policy_only']};rows=[]
    for row in j(ROOT/'eval/qwen35/a02/dev/questions-v2.json'):
        case=load_case(row['case_id']);p=plan(case,Transcript.parse(dict(request_id=row['id'],text=row['question'],source='typed',final=True)),[])
        assert p.route==row['expected_route']
        natural=row['id'] in model
        text=model[row['id']]['S2_text'] if natural else policies[row['id']]['text']
        verified=check(p,text)
        rows.append(dict(id=row['id'],question=row['question'],case_id=row['case_id'],route=p.route,
            source='BOARD_FULL_MODEL_RAW' if natural else 'PC_POLICY_TEMPLATE_NO_MODEL',raw_text=text,
            checker=verified,expected_facts=[asdict(f) for f in p.facts],
            number_surfaces=re.findall(r'[0-9]+(?:\.[0-9]+)?|[一二两三四五六七八九十]+',text),
            polarity_surfaces=[x for x in ('没有','不清楚','不','有') if x in text],
            EOS=model[row['id']]['EOS'] if natural else None,
            output_tokens=model[row['id']]['output_tokens'] if natural else None,
            raw_output_replaced=False,medical_review='PENDING_NOT_CLAIMED'))
    assert len(rows)==24 and len(model)==17 and len(policies)==7
    natural=[r for r in rows if r['source']=='BOARD_FULL_MODEL_RAW']
    template=[r for r in rows if r['source']=='PC_POLICY_TEMPLATE_NO_MODEL']
    counts=dict(Counter(r['checker']['status'] for r in natural))
    assert all(r['checker']['status']=='pass' for r in template)
    result=dict(status='PASS_DEV_FINITE_CHECKER' if counts=={'pass':17} else 'FAIL_OR_UNCERTAIN_DEV_RAW_OUTPUT_PRESERVED',
        rows=rows,items=24,model_items=17,policy_templates=7,policy_template_ratio=7/24,
        policy_routes=dict(Counter(r['route'] for r in template)),model_checker_counts=counts,
        model_EOS_count=sum(r['EOS'] for r in natural),model_token_limit=24,
        model_token_limit_without_EOS=[r['id'] for r in natural if not r['EOS'] and r['output_tokens']==24],
        no_automatic_fallback=True,finite_checker_is_not_medical_review=True,medical_review='PENDING_NOT_CLAIMED')
    save(OUT/'DEV_QUALITY.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
