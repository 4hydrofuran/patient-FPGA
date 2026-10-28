"""Frozen 25/7 wiring parity; model execution belongs to the explicit PC CLI."""
import ast
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
WEB=ROOT/'platform/qwen35/web'
sys.path.insert(0,str(WEB));sys.path.insert(0,str(WEB/'vendor/web_gateway/src'))
from short_prompt_adapter import prompt_messages
from patient_web.reference.domain import load_case,Transcript,digest
from patient_web.reference.planning import plan
from patient_web.reference.session import Session
from patient_web.reference.checking import prompt_messages as legacy_prompt,forms,check
from jinja2.sandbox import ImmutableSandboxedEnvironment

FACTS=ROOT/'evidence/model_pl_A/20261026-short-prompt-v1/facts-only-02'


class Tests(unittest.TestCase):
    def test_all_25_original_plans_messages_templates_and_fact_forms_match(self):
        cohort=json.loads((FACTS/'TOKENIZED_WORKLOADS.json').read_text(encoding='utf-8'))
        template=ImmutableSandboxedEnvironment().from_string((FACTS/'chat_template.jinja').read_text(encoding='utf-8'))
        count=0
        for row in cohort['real_inputs']:
            with self.subTest(id=row['id']):
                a=row['application'];case=load_case(a['case_id'])
                p=plan(case,Transcript.parse(dict(request_id=row['id'],text=a['question'],source='typed',final=True)),())
                self.assertEqual(digest(p.to_dict()),digest(a['plan']))
                self.assertEqual(case.sha256,a['case_sha256'])
                self.assertEqual(prompt_messages(p,a['question']),a['messages'])
                self.assertEqual(template.render(messages=prompt_messages(p,a['question']),add_generation_prompt=True,enable_thinking=False),row['prompt'])
                self.assertEqual(check(p,''.join(forms(f)[0]+'。' for f in p.facts))['status'],'pass')
                count+=1
        self.assertEqual(count,25)

    def test_original_score_ast_is_frozen(self):
        def functions(path):
            tree=ast.parse(path.read_text(encoding='utf-8'))
            return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        reference=WEB/'vendor/web_gateway/src/patient_web/reference'
        # Twenty-case integration intentionally extends routes and accepted surfaces.
        # The original cohort above still checks exact legacy messages/plans; scoring stays unchanged.
        self.assertEqual(functions(reference/'scoring.py'),functions(FACTS/'application/system_qwen35/app/scoring.py'))

    def test_internal_builder_keeps_default_prompt_and_raw_question_for_score(self):
        row=json.loads((FACTS/'WORKLOADS.json').read_text(encoding='utf-8'))['real_inputs'][3]
        text=row['application']['question'];captured=[]
        class Model:
            def generate(self,messages,**kw):
                captured.append(messages)
                return dict(text='每次疼痛持续10分钟。',status='OK',eos=True)
        for custom in (None,prompt_messages):
            s=Session('SYN_CP_01',software_test=True,prompt_builder=custom)
            r=s.submit(dict(request_id='raw',text=text,source='typed',final=True),Model(),180)
            self.assertEqual(r['answer_source'],'MODEL')
            self.assertEqual(s._events[0]['transcript'],text)
        self.assertIn('学生问题',captured[0][-1]['content'])
        self.assertEqual(captured[1],row['application']['messages'])

    def test_seven_policy_inputs_do_not_call_builder_or_model(self):
        cohort=json.loads((FACTS/'WORKLOADS.json').read_text(encoding='utf-8'))
        original={r['id']:r for r in json.loads((ROOT/'eval/qwen35/a02/dev/questions-v2.json').read_text(encoding='utf-8'))}
        def forbidden(*a,**kw):raise AssertionError('policy must not invoke prompt/model')
        class Never:
            generate=staticmethod(forbidden)
        for row in cohort['policy_inputs']:
            s=Session(original[row['id']]['case_id'],software_test=True,prompt_builder=forbidden)
            r=s.submit(dict(request_id=row['id'],text=row['question'],source='typed',final=True),Never(),180)
            self.assertEqual(r['llm_calls'],0);self.assertEqual(r['answer_plan']['route'],row['route'])

    def test_timeout_retains_original_fallback_and_nonnegative_stage_times(self):
        class Timeout:
            def generate(self,*a,**kw):raise TimeoutError('explicit fixture deadline')
        s=Session('SYN_CP_01',software_test=True,prompt_builder=prompt_messages)
        r=s.submit(dict(request_id='timeout',text='每次疼痛持续多久？',source='typed',final=True),Timeout(),180)
        self.assertEqual(r['answer_source'],'TIMEOUT')
        self.assertEqual(r['final_check']['status'],'pass')
        self.assertTrue(all(v>=0 for k,v in r['stage_timing'].items() if k.endswith('_ms')))


if __name__=='__main__':unittest.main()
