"""Protocol/budget fixtures only; real generation and latency use explicit CLIs."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
WEB=ROOT/'platform/qwen35/web'
EV=ROOT/'evidence/model_pl_A/20261027-realtime-miss-opt-v1'
sys.path.insert(0,str(WEB))
from board_case import load_native
from continuous_sessions import question_reserve
from realtime_draft import STRATEGY


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read=lambda p:json.loads(p.read_text(encoding='utf-8'))
        cls.ready=read(EV/'pairs198-t2-32/ready.json')
        proof=read(EV/'pairs198-t2-32/proof/pair-001-draft.json')
        cls.result=proof['result']
        cls.Native=load_native(ROOT/'system_qwen35/app',ROOT)
        cls.template=ROOT/'release/a12_fast_response_20261027_v2/short34-threads2/continuous/bundle/control/chat_template.jinja'

    def native(self,result=None,ready=None):
        result=copy.deepcopy(result or self.result)
        class Fixture:
            def send(self,request):self.request=request
            def get(self,timeout):return dict(result,id=self.request['id'])
            def close(self):return True
        return self.Native(Fixture(),ready or self.ready,max_output_tokens=32,domain='PC_REFERENCE',
                           template_path=self.template,generation_strategy=STRATEGY)

    def test_old_worker_cannot_silently_ignore_draft_selection(self):
        ready=copy.deepcopy(self.ready);ready.pop('realtime_draft')
        with self.assertRaisesRegex(RuntimeError,'capability'):
            self.native(ready=ready)

    def test_target_receipt_mismatch_refuses_and_marks_broken(self):
        result=copy.deepcopy(self.result)
        result['speculative_decoding']['target_greedy_tokens'][0]+=1
        native=self.native(result)
        with self.assertRaisesRegex(RuntimeError,'target model'):
            native.generate([{'role':'system','content':'fixture'},{'role':'user','content':'事实句：\n疼痛在胸骨后。'}])
        self.assertTrue(native.broken)

    def test_full_replay_must_be_confirmed_after_draft_rejection(self):
        result=copy.deepcopy(self.result)
        result['speculative_decoding'].update(accepted=False,fallback_full_prompt_replayed=False)
        native=self.native(result)
        with self.assertRaisesRegex(RuntimeError,'full original prompt'):
            native.generate([{'role':'system','content':'fixture'},{'role':'user','content':'事实句：\n疼痛在胸骨后。'}])

    def test_admission_covers_verification_and_complete_serial_replay(self):
        self.assertEqual(question_reserve(1024,34,24),10584)
        self.assertEqual(question_reserve(1024,34,32,draft_strategy=STRATEGY),22320)
        # The first pass appends <32 draft tokens inside the same 1024 bound.
        # Its ubatch calls plus the full original replay never exceed admission.
        for prompt in range(35,993):
            for proposed in (1,8,24,31):
                if prompt+32>1024:continue
                verify=72*((prompt+proposed-34+7)//8)
                replay=72*((prompt-34+7)//8+31)
                self.assertLessEqual(verify+replay,22320)


if __name__=='__main__':unittest.main()
