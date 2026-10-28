"""Profile admission and protocol fixtures; never invoke CPU or BOARD execution."""
import copy
import json
from pathlib import Path
import sys
import types
import unittest
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/web'))
from continuous_sessions import question_reserve,may_end
from fast_response_profile import check_ready,digest,validate_profile,pair_budget
from interactive_case import CachedTransport


def profile():
    tokens=list(range(34))
    return dict(schema='A12_FAST_RESPONSE_PROFILE_V1',profile_id='short34-threads2',prompt_policy='facts-only-02',
        prefix_tokens=34,prefix_token_ids=tokens,prefix_sha256=digest(tokens),cache_id='short34-t2',
        context_tokens=1024,output_tokens=24,threads=2,kernel_threads=2,
        authorization_included=False,prefix_identity=dict(threads=2,template_sha256='new'))


class Tests(unittest.TestCase):
    def test_34_and_70_reserves_cover_full_context_not_fixed_cohort(self):
        self.assertEqual(question_reserve(1024,34,24),10584)
        self.assertEqual(question_reserve(1024,70,24),10296)
        self.assertEqual(pair_budget([
            dict(tokens=list(range(55)),cache_policy='R0',op='generate',max_tokens=24),
            dict(tokens=list(range(34)),cache_policy='R0',op='cache_create',max_tokens=1),
            dict(tokens=list(range(55)),cache_policy='TT10_REQUIRE_HIT',op='generate',max_tokens=24)],34),4392)

    def test_new_identity_refuses_legacy_or_different_threads(self):
        p=validate_profile(profile())
        ready={'prefix_cache':dict(enabled=True,binding_sha256='live',identity=copy.deepcopy(p['prefix_identity']))}
        check_ready(p,ready)
        for key,value in (('threads',3),('template_sha256','old')):
            changed=copy.deepcopy(ready);changed['prefix_cache']['identity'][key]=value
            with self.assertRaisesRegex(RuntimeError,'identity differs'):check_ready(p,changed)
        changed=copy.deepcopy(p);changed['prefix_tokens']=70
        with self.assertRaises(ValueError):validate_profile(changed)

    def test_short_transport_is_unready_until_actual_warm_and_requires_current_binding(self):
        p=profile();sent=[];received=[]
        api=types.SimpleNamespace(receive=lambda *a,**kw:received.pop(0))
        worker=types.SimpleNamespace(send=sent.append)
        t=CachedTransport(worker,None,Path('/unused'),api,profile=p,maximum_questions=None)
        with self.assertRaisesRegex(RuntimeError,'warm'):t.send({'id':'a12-1'})
        ready={'prefix_cache':dict(enabled=True,binding_sha256='live',identity=p['prefix_identity'])}
        received.append(dict(type='cache_created',id='warm_prefix',status='OK',state_cleared_before_response=True,
            state_position_after_clear=-1,prefix_cache=dict(binding_sha256='live',entries=[dict(id=p['cache_id'],tokens=34)])))
        t.warm(ready,dict(id='warm_prefix',tokens=p['prefix_token_ids'],cache_id=p['cache_id']))
        t.send({'id':'a12-1','prompt':'actual'})
        self.assertEqual(sent[-1]['cache_policy'],'TT10_REQUIRE_HIT')
        self.assertEqual(sent[-1]['cache_id'],p['cache_id'])
        received.append(dict(type='result',prefix_cache_request=dict(hit=True,reused_tokens=34),
            prefix_cache=dict(binding_sha256='old',entries=[dict(id=p['cache_id'],tokens=34)])))
        with self.assertRaisesRegex(RuntimeError,'binding'):t.get(1)

    def test_finish_session_keeps_worker_and_host_stop_waits_for_inflight(self):
        args=dict(continuous=True,closed=True,model_requests=4,maximum_questions=None,broken=False)
        self.assertFalse(may_end(idle=True,**args))
        self.assertFalse(may_end(idle=False,stop_requested=True,**args))
        self.assertTrue(may_end(idle=True,stop_requested=True,**args))

    def test_insufficient_board_budget_is_refused_before_any_send(self):
        sent=[];worker=types.SimpleNamespace(send=sent.append,real=True,max_runs=10583,runs=0)
        t=CachedTransport(worker,None,Path('/unused'),object(),profile=profile())
        t.warm_result={}
        with self.assertRaisesRegex(RuntimeError,'budget'):t.send({'id':'never-sent'})
        self.assertEqual(sent,[])

    def test_missing_packaged_adapter_fails_before_owner_or_model(self):
        from fast_response_preflight import preflight
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'profile.json').write_text(json.dumps(profile()),encoding='utf-8')
            for name in ('web_managed.py','native_pl.py','fast_response_profile.py',
                         'web_gateway/src/patient_web/managed.py','web_gateway/src/patient_web/reference/session.py'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('',encoding='utf-8')
            with self.assertRaisesRegex(ImportError,'short_prompt_adapter'):
                preflight(root)


if __name__=='__main__':unittest.main()
