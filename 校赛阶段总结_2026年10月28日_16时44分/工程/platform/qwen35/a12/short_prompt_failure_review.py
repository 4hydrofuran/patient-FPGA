"""Review all existing short-prompt outputs against the same pinned finite checker.

Read-only model evidence analysis; no model run, new prompt or checker change.
Finite grammar observations are not medical equivalence judgments.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

from request_journal_verified import ROOT, FrozenProbe, canonical, digest, require

VARIANTS=('20261025-short-prompt-offline-v3',
          '20261025-short-prompt-copy-before-question-v1','20261025-short-prompt-verbatim-v1')


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    checker=FrozenProbe();rows=[];pins=[];groups=[];cohort=None
    for variant in VARIANTS:
        directory=ROOT/'evidence/model_pl_A'/variant
        inputs=json.loads((directory/'TOKENIZED_WORKLOADS.json').read_text(encoding='utf-8'))
        quality=json.loads((directory/'QUALITY.json').read_text(encoding='utf-8'))
        result=json.loads((directory/'RESULT.json').read_text(encoding='utf-8'))
        for name in ('TOKENIZED_WORKLOADS.json','QUALITY.json','RESULT.json'):
            path=directory/name;raw=path.read_bytes()
            pins.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        requests={r['id']:r for r in inputs['real_inputs']}
        require(len(requests)==25 and len(quality['rows'])==25 and len(quality['policy_items'])==7,'cohort size changed')
        current={k:(r['application']['case_id'],r['application']['question'],digest(r['application']['plan'])) for k,r in requests.items()}
        cohort=cohort or current;require(current==cohort,'cohort/facts changed between experiments')
        accepted=[];rejected=[]
        for q in quality['rows']:
            request=requests[q['id']];item=request['application'];case=checker.domain.load_case(item['case_id'])
            plan=checker.planning.plan(case,checker.domain.Transcript.parse(dict(request_id=q['id'],
                text=item['question'],source='typed',final=True)),())
            require(case.sha256==item['case_sha256'] and digest(plan.to_dict())==digest(item['plan']),
                    'frozen fact identity changed')
            check=checker.checking.check(plan,q['raw_model_text'])
            if q['eos'] is True:require(check==q['candidate'],'same-checker classification differs')
            is_pass=q['eos'] is True and check['status']=='pass' and q['answer_source']=='MODEL'
            (accepted if is_pass else rejected).append(q['id'])
            rows.append(dict(variant=variant,id=q['id'],question=item['question'],case_sha256=case.sha256,
                raw_model_text=q['raw_model_text'],eos=q['eos'],answer_source=q['answer_source'],
                same_finite_checker=check,accepted=is_pass,raw_rewritten=False,
                approved_relation_surfaces=[dict(slot=f.slot,status=f.status,value=f.value,unit=f.unit,
                    polarity=f.polarity,surfaces=checker.checking.forms(f)) for f in plan.facts],
                actual_numeric_surfaces=re.findall(r'[0-9]+(?:\.[0-9]+)?|[一二两三四五六七八九十]+',q['raw_model_text']),
                actual_polarity_markers=[s for s in ('没有','不清楚','不','有') if s in q['raw_model_text']],
                full_tokens=q['full_tokens'],reused_tokens=q['reused_tokens'],new_tokens=q['new_tokens'],
                medical_equivalence='NOT_REVIEWED',BOARD='NOT_TESTED'))
        require(rejected==quality['rejected']==result['quality_rejections'],'stored quality rejection list differs')
        require(all(p['llm_calls']==0 and p['final_check']['status']=='pass' for p in quality['policy_items']),
                'policy cases changed')
        groups.append(dict(variant=variant,accepted=len(accepted),total=25,rejected=rejected,
            prefix_tokens=result['prefix_tokens'],suffix_range=result['suffix_range'],
            suffix_16_to_24_count=result['suffix_16_to_24_count'],adopt=False))
    failed_ids=sorted({r['id'] for r in rows if not r['accepted']})
    matrix={name:[r for r in rows if r['id']==name] for name in failed_ids}
    summary=dict(status='PASS_REPRODUCED_EXISTING_REJECTIONS_ALL_VARIANTS_REMAIN_NOT_ACCEPTED',
        checked_model_outputs=75,model_items_per_variant=25,policy_items_per_variant=7,
        all_frozen_cohorts_and_facts_equal=True,same_checker_results_equal=True,
        variants=groups,union_rejected_ids=failed_ids,new_prompt_candidates=0,new_model_runs=0,PL_calls=0,
        checker_changes=0,BOARD='NOT_TESTED',latency_saving_s=None,medical_review='NOT_PERFORMED',
        decision='HOLD_ALL_THREE_SHORT_PROMPTS_KEEP_ORDINARY_PROBE_FROZEN')
    for name,value in [('RESULT.json',summary),('FAILURE_MATRIX.json',matrix),('SOURCE_FILES.json',pins)]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
    text='''# 短提示词失败复核

本次只重新检查既有75份模型原文及三组固定输入，没有重新运行模型、增加提示词或读取重型诊断。
三组25项的病例/问题/事实完全相同，原有限语法检查结果逐项一致；7项策略输入各保持零模型。
内容通过仍为20/25、20/25、21/25。全部方案继续NOT_ACCEPTED，普通探测包不变。

FAILURE_MATRIX.json保留所有方案在“任一方案曾失败”输入上的原始输出、原检查结果、该事实允许的完整关系表达及数字/肯否表面形式。
这能定位原文相对于既有语法、单位、未知表达的差异，不能据此宣布语句医学等价，不能放宽checker或改写原文后计为模型成功。
若继续处理这些差异，应将新的生成约束或提示词作为独立候选，保持事实/语法门槛并重新冻结全部输入；不继续叠加长诊断或复制指令来追求单个失败例通过。

命中后新算仍为35～46或25～36 token，16～24目标均为0/25；板端收益和输入到有效回答时延为null。
性能主线继续采用冻结普通包，日志候选独立验证。当前分析不为任何板端计算、释放、重放或正式性能验收提供授权。
'''
    with (out/'REPORT.md').open('x',encoding='utf-8') as f:f.write(text)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True,type=Path);args=p.parse_args()
    run(args.evidence)


if __name__=='__main__':main()
