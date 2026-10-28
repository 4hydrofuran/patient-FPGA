import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/web'))
from interactive_case import CachedTransport
from interactive_entry import graphical_platform, graphical_admission, graphical_main


class Tests(unittest.TestCase):
    def test_graphical_admission_uses_real_pool_and_retains_memory_floor(self):
        sys.path.insert(0,str(ROOT/'platform/qwen35/a12'))
        from capacity_policy import admission
        mem=dict(MemAvailable=3_000_000,CmaFree=40_000,CmaTotal=819_200)
        result=graphical_admission(admission,mem,140591104)
        self.assertTrue(result['allowed'])
        self.assertFalse(result['isolated_mode_allowed'])
        self.assertFalse(result['allocation_proven'])
        self.assertFalse(graphical_admission(admission,dict(mem,MemAvailable=1_200_000),140591104)['allowed'])
        self.assertFalse(graphical_admission(admission,dict(mem,CmaTotal=200_000),140591104)['allowed'])

    def test_graphical_entry_accepts_only_the_pinned_early_heuristic(self):
        source=(ROOT/'evidence/model_pl_A/20261026-pl-authfix-board-v2/bundle-fixed-v2/control/resource_probe_manager.py').read_text()
        self.assertIsInstance(graphical_main(source),types.CodeType)
        with self.assertRaises(RuntimeError):graphical_main(source.replace("initial['memory_kib']['CmaFree'] >= 32768","initial['memory_kib']['CmaFree'] >= 32769"))

    def test_warm_and_request_use_exact_binding_and_require_hit(self):
        sent=[]
        result=dict(type='cache_created',id='warm_prefix',status='OK',state_cleared_before_response=True,
            state_position_after_clear=-1,prefix_cache={'binding_sha256':'b','entries':[{'tokens':70}]})
        api=types.SimpleNamespace(receive=lambda *a,**kw:result)
        worker=types.SimpleNamespace(send=sent.append)
        t=CachedTransport(worker,object(),Path('/unused'),api)
        t.warm({'prefix_cache':{'binding_sha256':'b'}},{'id':'warm_prefix','op':'cache_create'})
        self.assertFalse(t.inflight)
        self.assertEqual(sent[0]['cache_binding_sha256'],'b')
        t.send({'id':'a12-1','cache_policy':'R0','prompt':'fixture'})
        self.assertEqual(sent[1]['cache_policy'],'TT10_REQUIRE_HIT')
        self.assertEqual(sent[1]['cache_id'],'neutral')
        self.assertEqual(sent[1]['cache_binding_sha256'],'b')
        with self.assertRaises(RuntimeError):t.send({'id':'second'})
        self.assertEqual(len(sent),2)

    def test_miss_is_not_silently_accepted(self):
        api=types.SimpleNamespace(receive=lambda *a,**kw:{'type':'result','prefix_cache_request':{'hit':False,'reused_tokens':0}})
        t=CachedTransport(object(),object(),Path('/unused'),api)
        with self.assertRaises(AssertionError):t.get(1)

    def test_graphical_variant_keeps_desktop_but_checks_existing_pl_holders(self):
        class Base:
            pl_mutation_started=False
            worker=None
            def emit(self,*a,**kw):pass
            def no_users(self,**kw):self.checked=kw
        platform=graphical_platform(Base)()
        with patch('interactive_entry.subprocess.run',return_value=types.SimpleNamespace(stdout='active\n')):
            platform.service('stop')
        self.assertFalse(platform.gdm_isolated)
        platform.wait_prepl_quiet()
        self.assertEqual(platform.checked,{'module_loaded':False})

if __name__=='__main__':unittest.main()
