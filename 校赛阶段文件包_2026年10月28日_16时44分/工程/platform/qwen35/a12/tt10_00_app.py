"""Measured application adapter; keeps production Session, routing and checking."""
import json
import time
from jinja2.sandbox import ImmutableSandboxedEnvironment
from system_qwen35.app.session import Session


class MeasuredBackend:
    def __init__(self, worker, receive, template, frozen):
        self.worker, self.receive, self.frozen = worker, receive, frozen
        self.template = template
        self.env = ImmutableSandboxedEnvironment()
        def fail(text): raise ValueError(text)
        self.env.globals['raise_exception'] = fail
        self.events = []
        self.stamps = {}

    def generate(self, messages, timeout_s=600):
        self.stamps['backend_enter_ns'] = time.monotonic_ns()
        prompt = self.env.from_string(self.template).render(
            messages=messages, add_generation_prompt=True, enable_thinking=False)
        assert prompt == self.frozen['prompt'], 'application prompt drift'
        assert prompt.endswith('<think>\n\n</think>\n\n')
        self.stamps['prompt_ready_ns'] = time.monotonic_ns()
        # Production prompt input: native tokenization stays inside the clock.
        req = {k:v for k,v in self.frozen.items() if k not in ('tokens','application')}
        self.stamps['worker_send_ns'] = time.monotonic_ns()
        self.worker.send(req)
        while True:
            r = self.receive()
            stamp = time.monotonic_ns()
            assert r.get('id') == req['id'], 'foreign response'
            if r['type'] == 'token':
                self.events.append(dict(index=r['index'], token=r['token'], received_monotonic_ns=stamp))
            if r['type'] in ('result','error'):
                self.stamps['worker_result_ns'] = stamp
                self.result = r
                break
        assert r['type']=='result' and r['status']=='OK' and r['gpu_layers']==0
        assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1
        assert r['prompt_tokens']==len(self.frozen['tokens'])
        return r


def measure(worker, receive, template, frozen):
    item = frozen['application']
    session = Session(item['case_id'], software_test=True)
    adapter = MeasuredBackend(worker, receive, template, frozen)
    # Session construction is service/session setup; route/template/tokenize are timed.
    begin = time.monotonic_ns()
    response = session.submit(dict(request_id=frozen['id'], text=item['question'],
                                   source='typed', final=True), adapter, 600)
    checked = time.monotonic_ns()
    assert hasattr(adapter,'result'), 'policy response is not a model baseline'
    first = adapter.events[0]['received_monotonic_ns'] if adapter.events else None
    stamps = dict(request_received_ns=begin, **adapter.stamps,
                  first_token_ns=first, checked_ns=checked)
    report = dict(schema='A12_TT10_APPLICATION_TIMING_V1', clock='Linux CLOCK_MONOTONIC',
                  stamps=stamps, TTFT_app_ms=(first-begin)/1e6 if first else None,
                  TTFT_worker_ms=(first-stamps['worker_send_ns'])/1e6 if first else None,
                  complete_app_ms=(checked-begin)/1e6,
                  prepare_before_worker_ms=(stamps['worker_send_ns']-begin)/1e6,
                  validated_after_worker_ms=(checked-stamps['worker_result_ns'])/1e6,
                  cache=dict(policy='R0_CLEAR_ALL_REPLAY',hit=False,
                             reason='TT10-01_NOT_IMPLEMENTED',new_tokens=len(frozen['tokens'])),
                  answer_source=response.get('answer_source'), candidate_check=response.get('candidate_check'),
                  final_check=response.get('final_check'), eos=adapter.result['eos'],
                  deadline_10s_violation=first is None or first-begin>10_000_000_000,
                  clinical_review='PENDING_TEACHER_REVIEW', software_test_only=True,
                  session_setup_outside_clock=True, response=response)
    return adapter.result, adapter.events, stamps['worker_send_ns'], stamps['worker_result_ns'], report
