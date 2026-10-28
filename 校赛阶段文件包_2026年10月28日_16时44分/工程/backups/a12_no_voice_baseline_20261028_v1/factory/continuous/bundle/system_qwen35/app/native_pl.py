"""Explicit A12 application adapter for an already owned native worker.

It never starts/kills an XRT process and never falls back to CPU. The platform
manager owns the worker, dual locks, lease, permits and final resource gates.
"""
import math
import threading
import time
from .native import ROOT
from jinja2.sandbox import ImmutableSandboxedEnvironment


class NativePL:
    def __init__(self, worker, ready, *, max_output_tokens, domain='BOARD'):
        expected='FPGA_REAL' if domain=='BOARD' else 'PC_MATH_DOUBLE'
        route=ready.get('bridge',{}).get('a12_route',{})
        if (ready.get('type')!='ready' or ready.get('execution_kind')!=expected or
            route.get('a12_route_scope')!='all' or ready.get('physical_ubatch')!=8 or
            ready.get('cache_policy')!='R0_CLEAR_ALL_REPLAY' or
            ready.get('attention_schedule')!='SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING' or
            ready.get('non_mlp_projection_schedule')!='STABLE_PER_TOKEN_SIMD_GEMV' or
            route.get('contract_sha256')!='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6'):
            raise RuntimeError('A12 full-range worker identity differs; no fallback')
        if not 1<=max_output_tokens<=64:raise ValueError('explicit bounded output required')
        self.worker=worker;self.ready=ready;self.expected=expected;self.max_output_tokens=max_output_tokens
        self.template=(ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja').read_text(encoding='utf-8')
        self.env=ImmutableSandboxedEnvironment();self.lock=threading.Lock();self.broken=False
        self.trace_context=None;self.count=0
        def fail(message):raise ValueError(message)
        self.env.globals['raise_exception']=fail

    def generate(self,messages,timeout_s=20):
        if not isinstance(timeout_s,(int,float)) or not math.isfinite(timeout_s) or timeout_s<=0:
            raise ValueError('positive finite deadline required')
        if not self.lock.acquire(blocking=False):raise RuntimeError('A12 model busy')
        try:
            if self.broken:raise RuntimeError('A12 session requires explicit state recovery')
            prompt=self.env.from_string(self.template).render(messages=messages,add_generation_prompt=True,enable_thinking=False)
            if not prompt.endswith('<think>\n\n</think>\n\n'):raise RuntimeError('non-thinking template differs')
            self.count+=1;rid='a12-'+str(self.count)
            req=dict(id=rid,prompt=prompt,max_tokens=self.max_output_tokens,logits_mode='final',cache_policy='R0')
            if self.trace_context:
                req.update(session_id=self.trace_context['session_id'],session_epoch=self.trace_context['epoch'])
            start=time.monotonic();self.worker.send(req)
            while True:
                r=self.worker.get(max(.001,timeout_s-(time.monotonic()-start)))
                if r.get('id')!=rid:raise RuntimeError('A12 response identity differs')
                if r['type']=='error':raise RuntimeError(r['message'])
                if r['type']=='result':
                    if r.get('status')!='OK' or r.get('partial_output_usable') is not True:
                        raise RuntimeError('A12 result refused')
                    if not r.get('state_cleared_before_response') or r.get('state_position_after_clear')!=-1:
                        raise RuntimeError('A12 recurrent/conv/KV clear not confirmed')
                    route=r.get('bridge',{}).get('a12_route',{})
                    kind=route.get('execution_kind') if self.expected=='FPGA_REAL' else route.get('a12_domain')
                    if kind!=self.expected:raise RuntimeError('A12 backend changed during request')
                    r['actual_backend']=self.expected;r['round_wall_ms']=(time.monotonic()-start)*1000
                    return r
        except BaseException:
            self.broken=True;raise
        finally:self.lock.release()

    def close(self):
        # On pending DMA/unknown completion this returns False and keeps ownership.
        return self.worker.close()
