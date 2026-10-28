"""Host protocol fixtures; performance evidence comes from actual model/browser runs."""
import copy
import json
from pathlib import Path
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/web'))
from fast_response_profile import digest,validate_profile
from interactive_case import CachedTransport
from neutral_prefixes import select_prefix,warm_requests


def profile():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    p=read(ROOT/'release/a12_realtime_model_draft_20261027_v1/realtime34-threads3-out32/continuous/profile.json')
    x=read(ROOT/'evidence/model_pl_A/20261027-realtime-tail-opt-v2/prefix198/EXTRA_PREFIX.json')
    p['additional_neutral_prefixes']=[x]
    p['prefix_identity']['neutral_prefix_choices_sha256']=digest([p['prefix_token_ids'],x['prefix_token_ids']])
    p['prefix_identity']['neutral_prefix_routing_sha256']=digest([x])
    return p


class Tests(unittest.TestCase):
    def test_scale_first_uses_original_full_severity_relation(self):
        sys.path.insert(0,str(ROOT/'platform/qwen35/web/vendor/web_gateway/src'))
        from answer_cache_build import enumerate_plans
        from severity_scale_prompt import prompt_messages,PUBLIC_SEVERITY_PREFIX
        from patient_web.reference.checking import check
        for case,plan in enumerate_plans():
            messages=prompt_messages(plan,'ignored')
            literal=messages[1]['content'].removeprefix('事实句：\n')
            self.assertEqual(check(plan,literal)['status'],'pass')
            if plan.required_fact_ids==('severity',):self.assertTrue(literal.startswith(PUBLIC_SEVERITY_PREFIX))

    def test_scale_first_profile_registers_case_free_43_tokens_and_four_threads(self):
        from severity_scale_prompt import POLICY,policy_sha256
        p=profile();p['threads']=p['kernel_threads']=4;p['cache_id']='short34-t4'
        p['prefix_identity'].update(threads=4,kernel_threads=4,live_miss_prompt_policy_sha256=policy_sha256())
        p['live_miss_prompt_policy']=POLICY
        extra=json.loads((ROOT/'evidence/model_pl_A/20261027-realtime-tail-opt-v2/scale-first-smoke/EXTRA_PREFIX.json').read_text(encoding='utf-8'))
        p['additional_neutral_prefixes']=[extra]
        p['prefix_identity']['neutral_prefix_choices_sha256']=digest([p['prefix_token_ids'],extra['prefix_token_ids']])
        p['prefix_identity']['neutral_prefix_routing_sha256']=digest([extra])
        self.assertEqual(validate_profile(p)['threads'],4)
        self.assertEqual(select_prefix(p,{'prompt':extra['neutral_text']+'6分。'})['prefix_tokens'],43)

    def test_longest_exact_input_prefix_and_primary_fallback(self):
        p=validate_profile(profile());extra=p['additional_neutral_prefixes'][0]
        self.assertEqual(select_prefix(p,{'prompt':extra['neutral_text']+' 6 分。'})['prefix_tokens'],37)
        self.assertEqual(select_prefix(p,{'prompt':p['neutral_text']+'左胸痛。'})['prefix_tokens'],34)
        self.assertEqual(select_prefix(p,{'tokens':p['prefix_token_ids']})['prefix_tokens'],34)

    def test_definition_with_case_value_is_rejected_even_with_updated_identity(self):
        p=profile();p['additional_neutral_prefixes'][0]['neutral_text']+=' 6'
        p['prefix_identity']['neutral_prefix_routing_sha256']=digest(p['additional_neutral_prefixes'])
        with self.assertRaisesRegex(ValueError,'unreviewed secondary'):validate_profile(p)

    def test_both_slots_warm_before_question_and_selected_receipt_required(self):
        p=profile();sent=[];received=[]
        api=types.SimpleNamespace(receive=lambda *a,**kw:received.pop(0))
        worker=types.SimpleNamespace(send=sent.append)
        t=CachedTransport(worker,None,Path('/unused'),api,profile=p,maximum_questions=None)
        ready={'prefix_cache':dict(enabled=True,binding_sha256='current',identity=p['prefix_identity'])}
        warm=warm_requests(p,dict(id='warm',tokens=p['prefix_token_ids'],cache_id=p['cache_id']))
        for i,request in enumerate(warm):
            received.append(dict(type='cache_created',id=request['id'],status='OK',state_cleared_before_response=True,
                state_position_after_clear=-1,prefix_cache=dict(binding_sha256='current',
                entries=[dict(id=r['cache_id'],tokens=len(r['tokens'])) for r in warm[:i+1]])))
            t.warm(ready,request)
            if i==0:
                with self.assertRaisesRegex(RuntimeError,'all selected'):t.send({'id':'early'})
        prompt=p['additional_neutral_prefixes'][0]['neutral_text']+' 6 分。'
        t.send({'id':'actual','prompt':prompt})
        self.assertEqual(sent[-1]['cache_id'],'severity37-t3')
        result=dict(type='result',prefill_chunk=256,prefix_cache_request=dict(hit=True,reused_tokens=37),
            prefix_cache=dict(binding_sha256='current',entries=[dict(id='severity37-t3',tokens=37)]))
        received.append(copy.deepcopy(result));self.assertEqual(t.get(1),result)
        t.send({'id':'wrong-receipt','prompt':prompt})
        result['prefix_cache_request']['reused_tokens']=34;received.append(result)
        with self.assertRaises(AssertionError):t.get(1)


if __name__=='__main__':unittest.main()
