"""Auditable lexical rules, not an extra model-based intent extraction call."""
from dataclasses import dataclass,asdict
import re
import unicodedata
from .domain import Fact

RULE_VERSION='route-v2-draft'
PATTERNS={
 'location':r'哪里|哪儿|哪个部位|什么部位|位置|部位|胸骨',
 'quality':r'什么感觉|疼像什么|痛像什么|怎么个疼|怎么个痛|怎样的痛|疼痛性质|痛的性质|压迫|针扎|烧灼',
 'onset':r'什么时候|何时|开始|起病|几小时前',
 'duration':r'持续|每次.*多久|一次.*多久|一回.*多久|多长时间',
 'severity':r'几分|严重|程度|多疼|多痛|疼得厉害',
 'radiation':r'放射|牵扯|其他地方|别的地方|肩膀|胳膊',
 'trigger':r'诱因|什么情况下|什么活动|加重|活动后',
 'relief':r'缓解|减轻|休息后|歇一歇.*好',
 'dyspnea':r'气短|喘不上气|喘不过气|呼吸困难|呼吸费力',
 'allergy':r'过敏',
 'medications':r'用药|服药|吃.*药|药物(?!过敏)|药名',
}
RESTRICTED=r'忽略|提示词|系统指令|开发者|system|developer|扮演医生|诊断|治疗|开药|处方|评分|量表|给.*分|满分|答案|所有.*病例|完整.*病例|另一个病例|其他病例|病例[二三两]|修改|改成|写入|删除|读取文件|<\|'
DOUBLE_NEG=r'不是没有|并非没有|不可能没有|没有不|并不是不|不能说没有'
CLARIFY='您想了解疼痛的哪个方面，请具体说明？'
REFUSE='我只能回答本次模拟中与问诊有关的问题。'
LOW_CONF='刚才的问题我没有听清，请再说一遍。'

@dataclass(frozen=True)
class AnswerPlan:
    intent_ids: tuple
    allowed_fact_ids: tuple
    required_fact_ids: tuple
    facts: tuple
    already_disclosed: tuple
    played_history: tuple
    unknown_policy: str
    answer_style: str
    max_sentences: int
    route: str
    reason: str
    evidence: tuple
    rule_version: str=RULE_VERSION
    def to_dict(self):return asdict(self)

def plan(case,transcript,played,*,asr_confirmed=False):
    raw=transcript.text;normalized=unicodedata.normalize('NFKC',raw).lower()
    evidence=[];slots=[];reason='explicit_rule';route='answer'
    if re.search(RESTRICTED,normalized):route,reason='refuse','restricted_or_injection'
    elif re.search(DOUBLE_NEG,normalized):route,reason='clarify','double_negation_ambiguous'
    elif transcript.source=='asr_final' and ((transcript.confidence is None and not asr_confirmed) or (transcript.confidence is not None and transcript.confidence<0.8)):route,reason='clarify','asr_review_required'
    else:
        for slot,pattern in PATTERNS.items():
            matches=list(re.finditer(pattern,raw))
            if matches:
                slots.append(slot)
                for m in matches:evidence.append({'slot':slot,'span':[m.start(),m.end()],'quote':raw[m.start():m.end()]})
        if not slots and re.fullmatch(r'(那)?(刚才|这个|那个)(呢|方面呢)?[？?]?',raw.strip()) and played:
            slots=list(played[-1]['fact_ids']);reason='last_played_fact_explicit_followup'
            evidence=[{'slot':s,'span':[0,len(raw)],'quote':raw,'context_turn':played[-1]['turn_id']} for s in slots]
        if 'onset' in slots and 'duration' in slots and re.search(r'从开始.*到现在',raw):
            slots.remove('duration');evidence=[e for e in evidence if e['slot']!='duration']
        if not slots:route,reason='clarify','unresolved_intent'
        elif len(slots)>2:route,reason='clarify','too_many_topics'
    if route!='answer':slots=[];evidence=[]
    disclosed=tuple(sorted({f for event in played for f in event['fact_ids']}))
    facts=tuple(case.fact(s) for s in slots)
    relevant=tuple({'turn_id':x['turn_id'],'text':x['text'],'fact_ids':x['fact_ids']} for x in played[-2:] if set(x['fact_ids'])&set(slots))
    return AnswerPlan(tuple(slots),tuple(slots),tuple(slots),facts,disclosed,relevant,
                      'explicit_unknown-v1-draft','first_person_short',2,route,reason,tuple(evidence))
