"""Use the unchanged checker's scale-first severity form; current model still generates."""
import hashlib
import json
from compact_fact_prompt import policy_sha256 as original_policy_sha256
from short_prompt_adapter import SYSTEM

POLICY='allowed-severity-scale-first-02'
PUBLIC_SEVERITY_PREFIX='按10分计算，我的疼痛是'


def prompt_messages(plan,question):
    from patient_web.reference.checking import forms
    if plan.route!='answer' or not plan.facts:raise ValueError('requires original answer plan')
    def choose(f):
        choices=forms(f)
        if f.slot=='severity' and f.status=='known':
            selected=PUBLIC_SEVERITY_PREFIX+str(f.value)+'分'
            if selected not in choices:raise ValueError('scale-first expression absent from original checker')
            return selected
        return min(choices,key=lambda s:(len(s),sum(c in '0123456789' for c in s),s))
    return [dict(role='system',content=SYSTEM),dict(role='user',content='事实句：\n'+''.join(choose(f)+'。' for f in plan.facts))]


def policy_sha256():
    value=dict(id=POLICY,parent=original_policy_sha256(),severity='existing original checker scale-first form',
        public_prefix=PUBLIC_SEVERITY_PREFIX,delivery='REAL_TARGET_GREEDY_VERIFY_OR_REAL_SERIAL; unchanged original checker')
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
