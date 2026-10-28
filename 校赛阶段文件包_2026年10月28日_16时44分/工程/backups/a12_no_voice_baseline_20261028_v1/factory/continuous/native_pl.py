"""Explicit A12 application adapter for an already owned native worker.

It never starts/kills an XRT process and never falls back to CPU. The platform
manager owns the worker, dual locks, lease, permits and final resource gates.
"""
import math
import hashlib
from pathlib import Path
import threading
import time
from .native import ROOT
from jinja2.sandbox import ImmutableSandboxedEnvironment


class NativePL:
    def __init__(self, worker, ready, *, max_output_tokens, domain='BOARD', template_path=None, generation_strategy=None):
        expected={'BOARD':'FPGA_REAL','PC':'PC_MATH_DOUBLE','PC_REFERENCE':'CPU_REFERENCE'}.get(domain)
        if expected is None:raise ValueError('explicit execution domain required')
        route=ready.get('bridge',{}).get('a12_route',{})
        identity_ok=(route.get('a12_route_scope')=='all' and
                     route.get('contract_sha256')=='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6')
        if domain=='PC_REFERENCE':
            identity_ok=(route.get('execution_kind')=='CPU_REFERENCE' and
                         ready.get('bridge',{}).get('contract_sha256')=='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6')
        if (ready.get('type')!='ready' or ready.get('execution_kind')!=expected or
            not identity_ok or ready.get('physical_ubatch')!=8 or
            ready.get('cache_policy')!='R0_CLEAR_ALL_REPLAY' or
            ready.get('attention_schedule')!='SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING' or
            ready.get('non_mlp_projection_schedule')!='STABLE_PER_TOKEN_SIMD_GEMV'):
            raise RuntimeError('A12 full-range worker identity differs; no fallback')
        if not 1<=max_output_tokens<=64:raise ValueError('explicit bounded output required')
        if generation_strategy is not None:
            from realtime_draft import STRATEGY
            if generation_strategy != STRATEGY or ready.get('realtime_draft') != STRATEGY:
                raise RuntimeError('selected real-time draft worker capability differs')
        self.generation_strategy=generation_strategy
        self.worker=worker;self.ready=ready;self.expected=expected;self.max_output_tokens=max_output_tokens
        self.template=Path(template_path or ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja').read_text(encoding='utf-8')
        self.env=ImmutableSandboxedEnvironment();self.lock=threading.Lock();self.broken=False
        self.trace_context=None;self.count=0
        def fail(message):raise ValueError(message)
        self.env.globals['raise_exception']=fail
        self.compiled_template=self.env.from_string(self.template)

    def generate(self,messages,timeout_s=20):
        if not isinstance(timeout_s,(int,float)) or not math.isfinite(timeout_s) or timeout_s<=0:
            raise ValueError('positive finite deadline required')
        if not self.lock.acquire(blocking=False):raise RuntimeError('A12 model busy')
        try:
            if self.broken:raise RuntimeError('A12 session requires explicit state recovery')
            entered=time.monotonic_ns()
            prompt=self.compiled_template.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
            rendered=time.monotonic_ns()
            if not prompt.endswith('<think>\n\n</think>\n\n'):raise RuntimeError('non-thinking template differs')
            self.count+=1;rid='a12-'+str(self.count)
            req=dict(id=rid,prompt=prompt,max_tokens=self.max_output_tokens,logits_mode='final',cache_policy='R0')
            if self.generation_strategy:
                from realtime_draft import fact_copy_draft
                req.update(draft_strategy=self.generation_strategy,draft_text=fact_copy_draft(messages))
            if self.trace_context:
                req.update(session_id=self.trace_context['session_id'],session_epoch=self.trace_context['epoch'])
            start=time.monotonic();sent=time.monotonic_ns();first=None;self.worker.send(req)
            while True:
                r=self.worker.get(max(.001,timeout_s-(time.monotonic()-start)))
                if r.get('id')!=rid:raise RuntimeError('A12 response identity differs')
                if r.get('type')=='token' and first is None:first=time.monotonic_ns()
                if r['type']=='error':raise RuntimeError(r['message'])
                if r['type']=='result':
                    if r.get('status')!='OK' or r.get('partial_output_usable') is not True:
                        raise RuntimeError('A12 result refused')
                    if not r.get('state_cleared_before_response') or r.get('state_position_after_clear')!=-1:
                        raise RuntimeError('A12 recurrent/conv/KV clear not confirmed')
                    if self.generation_strategy:
                        spec=r.get('speculative_decoding',{})
                        if (spec.get('strategy') != self.generation_strategy or spec.get('requested') is not True
                                or spec.get('answer_cache_used') is not False or spec.get('forced_output') is not False
                                or r.get('teacher_forced') is not False or r.get('eos') is not True):
                            raise RuntimeError('real-time target verification receipt differs')
                        if spec.get('accepted'):
                            output=r.get('output_tokens')
                            if (not isinstance(output,list) or spec.get('argmax_checks') != len(output)+1
                                    or spec.get('target_greedy_tokens',[])[:-1] != output
                                    or spec.get('proposed_tokens') != output or spec.get('target_eos_verified') is not True):
                                raise RuntimeError('draft tokens were not selected by the target model')
                        elif spec.get('used') and spec.get('fallback_full_prompt_replayed') is not True:
                            raise RuntimeError('rejected draft did not replay the full original prompt')
                    route=r.get('bridge',{}).get('a12_route',{})
                    kind=route.get('execution_kind') if self.expected in ('FPGA_REAL','CPU_REFERENCE') else route.get('a12_domain')
                    if kind!=self.expected:raise RuntimeError('A12 backend changed during request')
                    r['actual_backend']=self.expected;r['round_wall_ms']=(time.monotonic()-start)*1000
                    r['application_timing']=dict(clock='Python monotonic_ns', template_ms=(rendered-entered)/1e6,
                        adapter_entered_monotonic_ns=str(entered),worker_send_monotonic_ns=str(sent),
                        first_token_monotonic_ns=str(first) if first else None,
                        worker_wall_ms=(time.monotonic_ns()-sent)/1e6,
                        first_token_from_adapter_ms=(first-entered)/1e6 if first else None,
                        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                        session_id=(self.trace_context or {}).get('session_id'),
                        request_id=(self.trace_context or {}).get('request_id'),
                        stages_nested=True, health_and_owner_checks_in_worker_wall=True)
                    return r
        except BaseException:
            self.broken=True;raise
        finally:self.lock.release()

    def close(self):
        # On pending DMA/unknown completion this returns False and keeps ownership.
        return self.worker.close()
