"""Bounded PC host service over the original Session and private model gates.

One loaded worker, one neutral warm, no automatic replay or budget renewal.
The text acknowledgement method belongs to the trusted PC host, never a
student transcript. This module neither creates a Board owner nor releases it.
"""
import copy
import math
from pathlib import Path
import threading
import time
import inspect
import textwrap
from jinja2.sandbox import ImmutableSandboxedEnvironment
from resident_evidence import read, save
from resident_manager import Manager, AdmissionDenied
from resident_policy import IDS
from plm_journal import Journal, need
from request_journal_verified import digest
import plm_journal as journal_source
from modelpl_derive import Derive

d=Derive(textwrap.dedent(inspect.getsource(Journal.append)))
d.edit("'end_fsync':'END'", "'end_fsync':'END','app_end_fsync':'INPUT_END'")
app_append_text, APP_APPEND_EDITS=d.finish()
append_scope=dict(journal_source.__dict__)
exec(compile(app_append_text,'<application-journal-identical-durable-boundaries>','exec'),append_scope)


class ApplicationJournal(Journal):
    def append(self, event, **data):
        need(self.serial < 256 and self.size + 8192 <= 1024 * 1024,
             'bounded application journal capacity exhausted')
        return append_scope['append'](self, event, **data)


class ResidentService:
    def __init__(self, build, directory, *, cap=72):
        self.build_path = Path(build)
        self.directory = Path(directory)
        self.cap = cap
        self.manager = None
        self.journal = None
        self.session = None
        self.ready = self.closed = self.failed = False
        self.operation = threading.Lock()
        self.inputs = set()
        self.rejections = self.sessions = 0
        self.active_input = None
        self.generated = []
        self.cancelled = threading.Event()

    def _available(self):
        if self.manager is not None and self.manager.current_deadline is not None:
            need(time.monotonic_ns()<self.manager.current_deadline, 'resident application deadline expired')
        need(self.ready and not self.closed and not self.failed and
             not self.cancelled.is_set() and self.manager._guard(),
             'resident service unavailable; no implicit new window')

    def _boundary(self):
        self._available()
        ticket = self.manager.monitor.fence()
        return self.manager.monitor.authorize(ticket, guard=self.manager._guard)

    def _error(self, code, message, *, fatal=False):
        if fatal:
            self.failed = True
            if self.manager is not None and getattr(self.manager, 'page', None) is not None:
                self.manager._fail('application: ' + message)
        return dict(type='error', code=code, message=message[:400], tts_ready=False,
                    fatal=fatal, software_test_only=True, audio_played=False,
                    release_allowed=False, BOARD='NOT_TESTED')

    def _refuse(self, code, message):
        self.rejections += 1
        fatal = self.rejections > 8
        return self._error(code, message, fatal=fatal)

    def start(self):
        need(not self.ready and self.manager is None and not self.failed,
             'resident service cannot be restarted')
        started = time.monotonic_ns()
        try:
            m = self._initialize_manager()
            m.ready()
            m.run_warm()
            self.app = m.frozen.app
            self.renderer = ImmutableSandboxedEnvironment().from_string(
                Path(m.build['chat_template']).read_text(encoding='utf-8'))
            self.journal = ApplicationJournal(self.directory/'application-state', m.page.epoch, m._fail)
            self.journal.append('APPLICATION_READY', worker_pid=m.p.pid,
                                warm_result_sha256=digest(m.control_results[0]),
                                policy_sha256=m.build['resident_policy_sha256'],
                                software_test_only=True, release_allowed=False)
            self.ready = True
            fence = self._boundary()
            return dict(type='ready', worker_pid=m.p.pid, worker_start_ticks=m.worker_ticks,
                        startup_and_warm_s=(time.monotonic_ns()-started)/1e9,
                        weights=m.loads, warm_count=1, private_request_limit=9,
                        remaining_model_requests=8, delivery_fence=fence,
                        software_test_only=True, medical_review='PENDING_TEACHER_REVIEW',
                        actual_FPGA_calls=None, BOARD='NOT_TESTED', release_allowed=False)
        except BaseException as exc:
            return self._error('startup_failed', str(exc), fatal=True)

    def _initialize_manager(self):
        m = self.manager = Manager.__new__(Manager)
        m.page = m.p = None
        m.__init__(self.build_path, self.directory, cap=self.cap)
        return m

    def open_session(self, case_id, mode='training'):
        if not self.operation.acquire(blocking=False):
            return self._refuse('busy', 'single active host operation required')
        try:
            self._available()
            if self.session is not None and self.session.snapshot()['pending'] is not None:
                return self._refuse('delivery_pending', 'acknowledge or cancel the previous answer first')
            if self.sessions >= 24:
                return self._refuse('session_limit', 'bounded session count exhausted')
            try:
                session = self.app.session.Session(case_id, mode=mode, software_test=True)
            except (ValueError, PermissionError):
                return self._refuse('invalid_session', 'unknown synthetic case or session mode')
            if self.session is not None:
                self.session.finish()
            self.session = session
            self.sessions += 1
            snap = session.snapshot()
            self.journal.append('SESSION_OPEN', session_id=snap['session_id'], case_id=case_id,
                                case_sha256=snap['case_sha256'], application_epoch=snap['epoch'])
            fence = self._boundary()
            return dict(type='session_opened', session_id=snap['session_id'], case_id=case_id,
                        epoch=snap['epoch'], software_test_only=True, delivery_fence=fence)
        except BaseException as exc:
            return self._error('session_failed', str(exc), fatal=True)
        finally:
            self.operation.release()

    def submit(self, transcript, timeout_s=30):
        # Application receipt time includes routing, rendering, vocabulary,
        # admission, model execution, checks, durable END and the outer fence.
        received = time.monotonic_ns()
        if not self.operation.acquire(blocking=False):
            return self._refuse('busy', 'single active host operation required')
        m = self.manager
        try:
            self._available()
            if self.session is None:
                return self._refuse('missing_session', 'open a synthetic software-test session first')
            if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or not 0 < timeout_s <= 120:
                return self._refuse('invalid_deadline', 'deadline must be finite and within (0,120] seconds')
            try:
                t = self.app.domain.Transcript.parse(transcript)
            except ValueError:
                return self._refuse('invalid_transcript', 'original final transcript validation failed')
            if t.request_id in self.inputs:
                return self._refuse('duplicate_input', 'input ID already used; no replay')
            if len(self.inputs) >= 24:
                return self._refuse('input_limit', 'bounded external input count exhausted')
            snap = self.session.snapshot()
            if snap['pending'] is not None:
                return self._refuse('delivery_pending', 'acknowledge or cancel the previous answer first')
            self.inputs.add(t.request_id)
            self.active_input = copy.deepcopy(transcript)
            self.active_history = copy.deepcopy(snap['played'])
            case = self.app.domain.load_case(snap['case_id'])
            self.active_plan = self.app.planning.plan(case, t, self.active_history)
            self.active_case = case
            self.last_admission_refusal = None
            m.current_deadline = min(m.page.deadline, received+int(timeout_s*1e9))
            self.journal.append('INPUT_BEGIN', input=transcript, session_id=snap['session_id'],
                                case_sha256=case.sha256, plan_sha256=digest(self.active_plan.to_dict()),
                                received_ns=received, deadline_ns=m.current_deadline)
            need(time.monotonic_ns()<m.current_deadline, 'resident application deadline expired')
            response = self.session.submit(copy.deepcopy(transcript), self, timeout_s=timeout_s)
            if self.last_admission_refusal is not None:
                self.journal.append('INPUT_REFUSED', request_id=t.request_id,
                                    reason=self.last_admission_refusal, backend_submitted=False)
                return self._refuse('capacity', self.last_admission_refusal)
            need(response['type']=='validated_answer' and response['final_check']['status']=='pass',
                 'original session did not validate the answer')
            if self.active_plan.route=='answer':
                need(response['answer_source']=='MODEL' and response['llm_calls']==1,
                     'template/timeout cannot count as a model answer')
            else:
                need(response['answer_source']=='TEMPLATE' and response['llm_calls']==0,
                     'original policy route must not call the model')
            response.update(application_received_ns=received, worker_pid=m.p.pid,
                            warm_count=1, weight_loads=m.loads, original_plan_route=self.active_plan.route)
            prepared_sha = digest(response)
            save(self.directory/('input_'+str(len(self.inputs))+'-PREPARED.json'), response)
            self.journal.append('INPUT_END', request_id=t.request_id, prepared_response_sha256=prepared_sha,
                                answer_source=response['answer_source'], model_calls=response['llm_calls'],
                                native_request_id=(response.get('model_result') or {}).get('native_request_id'),
                                pending_text_sha256=self.session.snapshot()['pending']['text_sha256'])
            # All durable I/O above; no file operation between this fence and return.
            fence = self._boundary()
            delivered = time.monotonic_ns()
            response.update(input_to_verified_result_s=(delivered-received)/1e9,
                            application_delivered_ns=delivered, delivery_fence=fence,
                            prepared_response_sha256=prepared_sha,
                            timing_scope='APPLICATION_RECEIPT_TO_VERIFIED_RETURN_PC_NOT_TRANSPORT_FLUSH_OR_BOARD')
            return response
        except BaseException as exc:
            return self._error('input_failed', str(exc), fatal=True)
        finally:
            if m is not None:
                m.current_deadline = None
            self.active_input = None
            self.operation.release()

    def generate(self, messages, timeout_s):
        """Only original Session invokes this backend, with the active plan."""
        m = self.manager
        need(self.active_input is not None and self.operation.locked() and self.active_plan.route=='answer',
             'backend call outside original active Session')
        need(messages==self.app.checking.prompt_messages(self.active_plan, self.active_input['text']),
             'original facts-only prompt differs')
        if len(m.completed)>=len(IDS):
            self.last_admission_refusal='resident eight model requests exhausted'
            raise AdmissionDenied(self.last_admission_refusal)
        prompt = self.renderer.render(messages=messages, add_generation_prompt=True, enable_thinking=False)
        need(prompt.startswith(m.frozen.policy['neutral_text']), 'dynamic prompt not bound to neutral prefix')
        tokens = m.tokenize(prompt)
        need(tokens[:34]==m.frozen.prefix_tokens, 'actual dynamic tokenization differs from neutral prefix')
        r = dict(id=IDS[len(m.completed)], op='generate', prompt=prompt, tokens=tokens,
                 max_tokens=24, cache_policy='TT10_REQUIRE_HIT', cache_id='resident-neutral',
                 prefill_chunk=256, logits_mode='final', state_fingerprint=True,
                 profile=False, diagnostic_report=False,
                 application=dict(case_id=self.active_case.case_id, case_sha256=self.active_case.sha256,
                                  transcript=copy.deepcopy(self.active_input), trusted_played=self.active_history,
                                  plan=self.active_plan.to_dict()))
        try:
            result = m.execute(r)
        except AdmissionDenied as exc:
            self.last_admission_refusal=str(exc)
            raise
        self.generated.append(r['id'])
        return dict(text=result['text'], status=result['status'], eos=result['eos'],
                    actual_backend=m.provider.execution_kind, native_request_id=r['id'], result_sha256=digest(result))

    def acknowledge(self, request_id, epoch):
        if not self.operation.acquire(blocking=False):
            return self._refuse('busy', 'acknowledgement requires idle service')
        try:
            self._available()
            need(self.session is not None, 'session missing')
            self.session.trusted_delivery(request_id, epoch, kind='PC_TEXT_TEST_ACK')
            self.journal.append('HOST_TEXT_ACK', request_id=request_id, application_epoch=epoch,
                                kind='PC_TEXT_TEST_ACK', audio_played=False)
            fence = self._boundary()
            return dict(type='delivery_ack', kind='PC_TEXT_TEST_ACK', request_id=request_id,
                        epoch=epoch, audio_played=False, software_test_only=True, delivery_fence=fence)
        except (ValueError, TypeError):
            return self._refuse('invalid_ack', 'stale or foreign host text acknowledgement')
        except BaseException as exc:
            return self._error('ack_failed', str(exc), fatal=True)
        finally:
            self.operation.release()

    def cancel(self):
        # Active cancellation revokes BEFORE waiting for application/Session locks.
        if not self.operation.acquire(blocking=False):
            self.cancelled.set()
            return self._error('active_cancelled', 'active operation cancelled; retain dirty state', fatal=True)
        try:
            self._available()
            epoch = self.session.cancel() if self.session is not None else None
            self.journal.append('IDLE_CANCEL', application_epoch=epoch, active_model=False)
            fence = self._boundary()
            return dict(type='cancelled', epoch=epoch, active_model=False, delivery_fence=fence)
        except BaseException as exc:
            return self._error('cancel_failed', str(exc), fatal=True)
        finally:
            self.operation.release()

    def close(self):
        if not self.operation.acquire(blocking=False):
            return self._refuse('busy', 'normal close requires idle service')
        try:
            self._available()
            if self.session is not None and self.session.snapshot()['pending'] is not None:
                return self._refuse('delivery_pending', 'acknowledge or cancel before normal close')
            self.journal.append('APPLICATION_STOP', generated=list(self.generated), external_inputs=len(self.inputs))
            result = self.manager.normal_close()
            self.journal.normal_close()
            if self.session is not None:
                self.session.finish()
            self.closed = True
            return dict(type='closed', result=result, generated=list(self.generated),
                        software_test_only=True, actual_FPGA_calls=None, release_allowed=False)
        except BaseException as exc:
            return self._error('close_failed', str(exc), fatal=True)
        finally:
            self.operation.release()
