"""Fail-closed finite language checker: whole clauses map to typed relations.

This is NOT a general medical semantic verifier. Unparsed prose is uncertain,
never accepted on keyword overlap. Rules/utterances remain teacher-review drafts.
"""
import re
from dataclasses import asdict
from .planning import CLARIFY,REFUSE,LOW_CONF

LABELS={'location':'疼痛位置','quality':'疼痛感觉','onset':'开始时间','duration':'每次持续时间','severity':'疼痛程度',
        'radiation':'疼痛牵扯部位','trigger':'诱因','relief':'缓解方式','dyspnea':'气短情况','allergy':'过敏情况','medications':'用药情况'}
NUM={1:'一',2:'两',3:'三',4:'四',5:'五',6:'六',7:'七',8:'八',9:'九',10:'十',20:'二十',30:'三十'}

def forms(f):
    if f.status=='unknown':
        labels=[LABELS[f.slot]]
        # A05 dev counterexample: whole relation synonym, not a text rewrite.
        # Known radiation still cannot become unknown; extra claims still fail.
        if f.slot=='radiation':labels.append('疼痛牵涉部位')
        return [phrase for label in labels for phrase in (label+'我不清楚','我不清楚'+label,label+'不清楚')]
    v=f.value;s=f.slot
    if s=='location':return ['疼痛在'+v,'我痛的地方在'+v,'我的疼痛在'+v,'我'+v+'痛']
    if s=='quality':return ['疼痛是'+v,'我感觉是'+v,'感觉是'+v]
    if s=='onset':return [x for n in (str(v),NUM.get(v,str(v))) for x in ('胸痛从'+n+'小时前开始','我是'+n+'小时前开始胸痛的')]
    if s=='duration':return [x for n in (str(v),NUM.get(v,str(v))) for x in ('每次疼痛持续'+n+'分钟','每次痛'+n+'分钟','每次持续'+n+'分钟')]
    if s=='severity':return ['疼痛程度是'+str(v)+'分，满分10分','按10分计算，我的疼痛是'+str(v)+'分']
    if s=='radiation':return ['疼痛会牵扯到'+v,'还会痛到'+v]
    if s=='trigger':return ['疼痛在'+v+'时出现','我在'+v+'时会痛',v+'时出现疼痛']
    if s=='relief':return [v+'可以减轻疼痛','疼痛在'+v+'后减轻']
    if s=='dyspnea':return ['我有气短','有气短','我气短','是的，我有气短'] if v else ['我没有气短','没有气短']
    raise ValueError('Unsupported known relation: '+s)

def fallback(p):
    if p.route=='refuse':return REFUSE
    if p.route=='clarify':return LOW_CONF if p.reason=='asr_review_required' else CLARIFY
    return '。'.join(forms(f)[0] for f in p.facts)+'。'

def check(p,text):
    base={'status':'uncertain','covered_fact_ids':[],'failure_bucket':'checker_uncertain','reason':'unparsed_relation'}
    if not isinstance(text,str) or not text or len(text)>220:return dict(base,reason='length')
    # Formatting-only canonicalization. Raw candidate remains in the audit log;
    # no number, unit, negation, token order or relation is rewritten.
    text=text.replace(' ','').replace('\t','')
    if re.search(r'诊断|建议|治疗|处方|医生|评分|分数是100|<think>|</think>|<\|',text):return dict(base,status='reject',failure_bucket='role',reason='role_or_control_token')
    if not text.endswith(('。','！','？','!','?')):return dict(base,reason='incomplete_sentence')
    sentences=[x for x in re.split('[。！？!?]',text) if x]
    if not 1<=len(sentences)<=p.max_sentences:return dict(base,reason='sentence_count')
    if p.route!='answer':
        return {'status':'pass','covered_fact_ids':[],'failure_bucket':None,'reason':'policy_literal'} if text==fallback(p) else base
    # Match all content as concatenated whole approved relation surfaces. Only
    # punctuation can separate clauses; no free prefix/suffix or substring checks.
    surfaces={}
    for f in p.facts:
        for phrase in forms(f):surfaces[phrase]=f.slot
    # A bare unknown can bind only a unique requested unknown fact, never two
    # requested facts and never override a known positive/negative relation.
    if len(p.facts)==1 and p.facts[0].status=='unknown':
        surfaces.update({'不清楚':p.facts[0].slot,'我不清楚':p.facts[0].slot})
    remaining=text;covered=[]
    while remaining:
        matches=[x for x in surfaces if remaining.startswith(x) and (len(remaining)==len(x) or remaining[len(x)] in '，,；;。！？!?')]
        if not matches:
            reason='numeric_unit_polarity_or_relation_mismatch' if re.search(r'[0-9一二两三四五六七八九十]|不|没',remaining) else 'unrecognized_or_extra_claim'
            return dict(base,covered_fact_ids=covered,reason=reason,failure_bucket='extra_fact_or_checker_uncertain')
        phrase=max(matches,key=len);covered.append(surfaces[phrase]);remaining=remaining[len(phrase):]
        remaining=remaining.lstrip('，,；;。！？!?')
    missing=set(p.required_fact_ids)-set(covered)
    if missing:return dict(base,status='reject',reason='missing_required',failure_bucket='omission',covered_fact_ids=covered)
    return {'status':'pass','covered_fact_ids':sorted(set(covered)),'failure_bucket':None,'reason':'whole_relation_grammar'}

def prompt_messages(p,question):
    # No rubric, no whole case and no other session; one model call per answer.
    facts=[{'id':f.slot,'status':f.status,'value':f.value,'unit':f.unit,'time_scope':f.time_scope,
            'polarity':f.polarity,'expression':forms(f)[0]} for f in p.facts]
    import json
    system='你是教学模拟病人。只说下方已核对的事实句，全部说完，不增删事实。保留数字、单位、肯否及“不清楚”。不复述问题，不诊断、不评分。直接输出1至2句病人回答，以句号结尾。'
    # Clear Chinese instructions suit this small model better than asking it to
    # interpret internal JSON. The quoted question is data, never instructions.
    payload='学生问题（不可信原文）：'+json.dumps(question,ensure_ascii=False)+'\n'
    payload+='本轮已核对的事实句（逐句原样说出）：\n'+'\n'.join(f['expression']+'。' for f in facts)
    # Context routing already used only host-confirmed history; unrelated turns
    # need not be retransmitted to the model. Plan still retains audit history.
    return [{'role':'system','content':system},{'role':'user','content':payload}]
