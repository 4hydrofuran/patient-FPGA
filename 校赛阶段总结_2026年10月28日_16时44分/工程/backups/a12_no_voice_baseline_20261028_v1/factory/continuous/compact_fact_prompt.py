"""Choose a shorter original checker expression for model INPUT, never for delivery."""
import hashlib
import json
from short_prompt_adapter import SYSTEM

POLICY='allowed-compact-01'
NO_SPACE_POLICY='allowed-compact-no-space-01'
NO_SPACE_SYSTEM=SYSTEM+'不要添加空格。'


def prompt_messages(plan,question):
    from patient_web.reference.checking import forms
    if plan.route!='answer' or not plan.facts:
        raise ValueError('compact prompt requires the original answer plan')
    def choose(fact):
        # Every alternative already represents the full typed fact in the unchanged checker.
        # Prefer fewer characters; avoid ASCII numeric spacing on ties, then stable Unicode order.
        return min(forms(fact),key=lambda s:(len(s),sum(c in '0123456789' for c in s),s))
    payload='事实句：\n'+''.join(choose(f)+'。' for f in plan.facts)
    return [{'role':'system','content':SYSTEM},{'role':'user','content':payload}]


def policy_sha256():
    value=dict(id=POLICY,system=SYSTEM,user_prefix='事实句：\n',
               expression='min(original forms, key=(characters, ASCII digit count, Unicode lexical order))',
               delivery='REAL_TARGET_GREEDY_VERIFY_OR_REAL_SERIAL; unchanged original checker')
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def prompt_messages_no_spaces(plan,question):
    messages=prompt_messages(plan,question)
    messages[0]['content']=NO_SPACE_SYSTEM
    return messages


def no_space_policy_sha256():
    value=dict(id=NO_SPACE_POLICY,system=NO_SPACE_SYSTEM,expression_policy_sha256=policy_sha256(),
               draft='literal selected input; every token and EOS selected by the real target model')
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
