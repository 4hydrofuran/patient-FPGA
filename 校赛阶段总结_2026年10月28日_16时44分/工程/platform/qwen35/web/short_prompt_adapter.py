"""Host-selected facts-only-02 prompt; the original planner/checker own facts."""
import hashlib
import json

SYSTEM = '你是模拟病人。请逐字复制用户提供的事实句，必须保留每个字及句号，不要解释。'
POLICY_ID = 'facts-only-02'


def prompt_messages(plan, question):
    # The question remains in Session and scoring, not in the model's fact payload.
    from patient_web.reference.checking import forms
    if plan.route != 'answer' or not plan.facts:
        raise ValueError('facts-only generation requires an original answer plan')
    payload = '事实句：\n' + ''.join(forms(f)[0] + '。' for f in plan.facts)
    return [{'role':'system','content':SYSTEM},{'role':'user','content':payload}]


def policy_sha256():
    value = dict(id=POLICY_ID, system=SYSTEM, user_prefix='事实句：\n',
                 facts='original forms(f)[0] + 。; concatenate without newline')
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()
