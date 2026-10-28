"""Short patient wording from the current typed facts; no whole-case prompt."""
import hashlib
import json

POLICY = 'patient-natural-short-v1'
# The small target model's unconstrained rewrites lost facts in pilot01/02.
# Naturalness comes from varied patient surfaces, with its proven complete-read prompt.
from short_prompt_adapter import SYSTEM


def prompt_messages(plan, question):
    from patient_web.reference.checking import natural_forms
    if plan.route != 'answer' or not plan.facts:
        raise ValueError('natural answer requires current facts')
    # Stable patient phrasing varies across cases/slots without changing the fact.
    sentences = []
    for fact in plan.facts:
        choices = natural_forms(fact)
        signature = json.dumps([fact.slot, fact.value, fact.time_scope], ensure_ascii=False)
        index = int(hashlib.sha256(signature.encode()).hexdigest()[:8], 16) % len(choices)
        sentences.append(choices[index] + '。')
    return [dict(role='system', content=SYSTEM),
            dict(role='user', content='事实句：\n' + ''.join(sentences))]


def policy_sha256():
    return hashlib.sha256(json.dumps(dict(id=POLICY, system=SYSTEM,
        selection='typed-fact SHA256 stable surface; target model generates all output',
        prompt='facts only; at most two; no unrelated history'),
        ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
