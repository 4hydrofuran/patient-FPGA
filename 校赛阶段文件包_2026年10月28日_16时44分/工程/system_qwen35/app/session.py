"""A02 single-session application state; only trusted host confirms delivery."""
from copy import deepcopy
from dataclasses import asdict
import time
import uuid
import threading
import math
from functools import wraps
from .domain import load_case,Transcript,digest
from .planning import plan
from .checking import check,fallback,prompt_messages
from .scoring import evidence,score

def exclusive(method):
    @wraps(method)
    def call(self,*args,**kwargs):
        if not self._operation.acquire(blocking=False):raise RuntimeError('Session operation in progress; no concurrent mutation')
        try:return method(self,*args,**kwargs)
        finally:self._operation.release()
    return call

class Session:
    def __init__(self,case_id,mode='training',*,software_test=False,prompt_builder=None):
        if mode not in ('training','exam'):raise ValueError('mode')
        self._case=load_case(case_id)
        if not software_test:raise PermissionError('Teacher review pending: only explicit software-test sessions are enabled')
        self._mode=mode;self._id=uuid.uuid4().hex;self._epoch=0
        self._events=[];self._played=[];self._received={};self._pending=None
        self._turn=0;self._closed=False
        self._operation=threading.Lock()
        self.prompt_builder=prompt_messages if prompt_builder is None else prompt_builder
    @property
    def epoch(self):return self._epoch
    def snapshot(self):
        return deepcopy({'session_id':self._id,'epoch':self._epoch,'case_id':self._case.case_id,
                         'case_version':self._case.version,'case_sha256':self._case.sha256,
                         'received':self._events,'played':self._played,'pending':self._pending,'closed':self._closed})
    @exclusive
    def submit(self,request,backend,timeout_s=20,*,trusted_asr_confirmation=None):
        if self._closed:raise RuntimeError('Session ended')
        if type(timeout_s) not in (int,float) or not math.isfinite(timeout_s) or timeout_s<=0:raise ValueError('Positive finite deadline required')
        t=Transcript.parse(request);fingerprint=digest(asdict(t))
        if t.request_id in self._received:
            old=self._received[t.request_id]
            if old['fingerprint']!=fingerprint:raise ValueError('Duplicate request ID with changed transcript')
            response=deepcopy(old['response'])
            if response.get('epoch')!=self._epoch or not self._pending or self._pending['request_id']!=t.request_id:
                response.update(tts_ready=False,replayed_receipt=True,invalidated=response.get('epoch')!=self._epoch)
            return response
        if self._pending is not None:raise RuntimeError('Prior validated response awaits delivery/cancel')
        if self._turn>=200:raise RuntimeError('Session turn bound reached')
        self._turn+=1;begin=time.monotonic_ns()
        if trusted_asr_confirmation is not None:
            # Operator-only software-fixture confirmation; never an ASR confidence
            # or medical approval. Raw ASR remains unchanged and scoring still
            # marks confidence=null as requiring review.
            kind=trusted_asr_confirmation.get('kind')
            if t.source!='asr_final' or kind not in ('SYNTHETIC_FIXTURE_EXACT_TRANSCRIPT','HUMAN_VERIFIED_RAW_TRANSCRIPT') or trusted_asr_confirmation.get('raw_text_digest')!=digest(t.text):raise ValueError('Invalid trusted ASR confirmation')
            if kind=='HUMAN_VERIFIED_RAW_TRANSCRIPT' and trusted_asr_confirmation.get('human_review') is not True:raise ValueError('Explicit human confirmation required')
        p=plan(self._case,t,self._played,asr_confirmed=trusted_asr_confirmation is not None)
        self._events.append(evidence(t,p,self._turn))
        candidate=None;llm_result=None;failure=None;checks=None;reason=None;calls=0
        if p.route!='answer':
            text=fallback(p);source='TEMPLATE';reason=p.reason
        else:
            calls=1
            try:
                llm_result=backend.generate(self.prompt_builder(p,t.text),timeout_s=timeout_s)
                candidate=llm_result['text'];checks=check(p,candidate)
                if llm_result.get('status')!='OK' or not llm_result.get('eos'):
                    checks={'status':'uncertain','failure_bucket':'incomplete_generation','reason':'non_eos_or_error'}
                if checks['status']=='pass':text=candidate;source='MODEL'
                else:text=fallback(p);source='TEMPLATE';reason='checker_rejected';failure=checks['failure_bucket']
            except TimeoutError as exc:
                text=fallback(p);source='TIMEOUT';reason='generation_deadline';failure='timeout'
                llm_result={'error':str(exc),'actual_backend':'CPU_REFERENCE','status':'TIMEOUT'}
            except RuntimeError as exc:
                # Fail explicitly for a missing/crashed backend. It is not a timeout
                # or a silent CPU/hardware fallback and no TTS text is issued.
                response={'type':'error','request_id':t.request_id,'epoch':self._epoch,'answer_source':None,
                          'failure_bucket':'backend_error','message':str(exc),'tts_ready':False}
                self._received[t.request_id]={'fingerprint':fingerprint,'response':response}
                return deepcopy(response)
        final_check=check(p,text)
        if final_check['status']!='pass':raise RuntimeError('Trusted fallback failed its own relation check')
        validated=time.monotonic_ns()
        response={'type':'validated_answer','session_id':self._id,'epoch':self._epoch,'turn_id':self._turn,
            'request_id':t.request_id,'case_id':self._case.case_id,'case_version':self._case.version,'case_sha256':self._case.sha256,
            'text':text,'answer_source':source,'fallback_reason':reason,'failure_bucket':failure,
            'candidate':candidate,'candidate_check':checks,'final_check':final_check,'answer_plan':p.to_dict(),
            'llm_calls':calls,'model_result':llm_result,'received_ns':begin,'validated_ns':validated,
            'tts_ready':True,'tts_executed':False,'audio_played':False,'software_test_only':True,
            'medical_review':'PENDING_TEACHER_REVIEW','asr_confirmation':trusted_asr_confirmation}
        self._pending={'request_id':t.request_id,'turn_id':self._turn,'epoch':self._epoch,'text':text,
                       'fact_ids':list(p.required_fact_ids),'text_sha256':digest(text)}
        self._received[t.request_id]={'fingerprint':fingerprint,'response':deepcopy(response)}
        return deepcopy(response)
    @exclusive
    def trusted_delivery(self,request_id,epoch,*,kind):
        # Not exposed on the student request channel. A03 must wire real playback
        # completion here; A02 permits only an explicitly labelled text-test ack.
        if kind!='PC_TEXT_TEST_ACK':raise ValueError('Audio playback not implemented in A02')
        p=self._pending
        if not p or p['request_id']!=request_id or epoch!=self._epoch:raise ValueError('Stale/foreign delivery ack')
        self._played.append(dict(p,delivery_kind=kind,audio_played=False));self._pending=None
    @exclusive
    def cancel(self):
        self._pending=None;self._epoch+=1
        # Native worker always uses R0 clear/replay. Rejected/generated-but-unplayed
        # text never enters prompt_messages; no KV-only rollback is attempted.
        return self._epoch
    @exclusive
    def trusted_playback_delivery(self,request_id,epoch,receipt):
        p=self._pending
        if not p or p['request_id']!=request_id or epoch!=self._epoch:raise ValueError('Stale playback')
        if receipt.get('cancelled') is not False or receipt.get('text_digest')!=p['text_sha256'] or receipt.get('playback_api_completed') is not True:raise ValueError('Incomplete/foreign playback')
        self._played.append(dict(p,delivery_kind='PLAYBACK_API_DRAIN',audio_played=None,acoustic_verified=False,receipt=deepcopy(receipt)))
        self._pending=None
    @exclusive
    def finish(self):self._closed=True;self._pending=None
    def training_feedback(self):
        if self._mode=='exam' and not self._closed:raise PermissionError('Exam feedback withheld until finish')
        return score(deepcopy(self._events))
    def recompute_score_for_host(self):return score(deepcopy(self._events))
