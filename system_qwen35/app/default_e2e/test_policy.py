import unittest
from .policy import registry,profile,new_trace,HardwareUnavailable
from ..domain import Transcript,load_case
from ..planning import plan
from ..checking import check,fallback,prompt_messages
from .prompts import prepare

class PolicyTests(unittest.TestCase):
    def test_default(self):
        for mode in ('cpu_same_math','no_hardware'):
            r=registry(mode);self.assertEqual(r['actual_backend'],'CPU_REFERENCE');self.assertEqual(r['fallback'],'disabled')
    def test_hardware_fails_before_startup(self):
        with self.assertRaises(HardwareUnavailable):registry('fpga_required')
    def test_candidates_not_silent_fallback(self):
        for linear,voice in [('B','A'),('A','C'),('missing','missing')]:
            with self.assertRaises(RuntimeError):registry(linear=linear,voice=voice)
    def test_thread_profiles(self):
        for llm in (2,3):
            for tts in (1,2):
                r=profile(llm,tts);self.assertEqual(r['kernel_threads'],llm);self.assertEqual(r['active_turns'],1)
        for pair in [(True,1),(4,1),(2,3),(0,2)]:
            with self.assertRaises(ValueError):profile(*pair)
    def test_null_is_not_zero(self):
        tr=new_trace('s',0,'r','no_hardware',True)
        self.assertTrue(all(x is None for x in tr['timestamps'].values()));self.assertIsNone(tr['actual_backend'])
    def test_prompt_payload_facts_unchanged(self):
        # Static preservation check, model-dependent quality has separate real tests.
        t=Transcript.parse({'request_id':'r','text':'每次疼痛持续多久，有没有气短？','source':'typed','final':True})
        p=plan(load_case('SYN_CP_01'),t,[]);m=prompt_messages(p,t.text)
        self.assertEqual(len(p.required_fact_ids),2);self.assertIn('我有气短',m[1]['content'])
        self.assertEqual(check(p,fallback(p))['status'],'pass')
        self.assertNotEqual(check(p,fallback(p).replace('我有气短','我没有气短'))['status'],'pass')
    def test_v4_single_fact_byte_identity_and_multi_fact_preservation(self):
        import json
        from .policy import ROOT
        dev=json.loads((ROOT/'eval/qwen35/a02/dev/questions-v2.json').read_text(encoding='utf-8'))
        for case in ('SYN_CP_01','SYN_CP_02','SYN_CP_03'):
            dev.append({'case_id':case,'question':'每次疼痛持续多久，有没有气短？'})
        count=0
        for d in dev:
            t=Transcript.parse({'request_id':'r','text':d['question'],'source':'typed','final':True});p=plan(load_case(d['case_id']),t,[])
            if p.route!='answer':continue
            old=prompt_messages(p,t.text);new,m=prepare(old,'facts_v4');_,before=prepare(old,'old');count+=1
            self.assertEqual(m['fact_requirement_sha256'],before['fact_requirement_sha256'])
            self.assertEqual(m['question_payload_sha256'],before['question_payload_sha256'])
            self.assertEqual(new[0],old[0])
            if len(p.facts)==1:self.assertEqual(new,old)
            else:self.assertEqual(check(p,new[1]['content'].split('：\n')[-1])['status'],'pass')
        self.assertEqual(count,20)
if __name__=='__main__':unittest.main()
