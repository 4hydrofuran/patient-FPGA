"""Single-flight consultation coordinator and authoritative browser snapshots."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
import logging
import threading
import uuid

from .errors import GatewayError, OperationCancelled
from .events import EventJournal
from .evaluation import build_evaluation

LOG = logging.getLogger(__name__)


@dataclass
class Conversation:
    business: object
    epoch: int = 0
    closed: bool = False
    turns: list = field(default_factory=list)
    commands: dict = field(default_factory=dict)
    evaluation: dict | None = None


@dataclass
class Work:
    session_id: str
    request_id: str
    epoch: int
    operation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cancelled: threading.Event = field(default_factory=threading.Event)


class Coordinator:
    def __init__(self, engine_factory, backend_name="native", journal_capacity=256):
        self.factory = engine_factory
        self.backend_name = backend_name
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="consultation")
        self.journal = EventJournal(journal_capacity)
        self.engine = None
        self.phase = "STARTING"
        self.failure = None
        self.conversations = {}
        self.starts = {}
        self.current_session = None
        self.work = None
        self.stopping = False
        self.initialized = threading.Event()
        self.started = False

    def start(self):
        with self.lock:
            if self.started:
                return
            self.started = True
            self.executor.submit(self._initialize)

    def _initialize(self):
        try:
            engine = self.factory()
            with self.lock:
                self.engine = engine
                self.phase = "READY"
                self.journal.emit("service.ready", backend=self.backend_name)
        except Exception as error:
            LOG.exception("Backend initialization failed")
            with self.lock:
                self.failure = error if isinstance(error, GatewayError) else GatewayError(
                    "BACKEND_START_FAILED", "后端启动失败，请检查本机服务日志。", 503)
                self.phase = "FAILED"
                self.journal.emit("service.failed", code=self.failure.code, message=self.failure.message)
        finally:
            self.initialized.set()

    def _require_ready(self):
        if self.stopping:
            raise GatewayError("SERVICE_STOPPING", "服务正在停止。", 503)
        if self.failure:
            raise self.failure
        if self.engine is None:
            raise GatewayError("NOT_READY", "后端仍在加载。", 503, True)
        if not self.engine.healthy:
            raise GatewayError("BACKEND_UNAVAILABLE", "模型不可用，需要重启服务后再试。", 503)

    def _conversation(self, session_id):
        if session_id not in self.conversations:
            raise GatewayError("SESSION_NOT_FOUND", "会话不存在或服务已重新启动。", 404)
        return self.conversations[session_id]

    def _idle(self):
        if self.work is not None:
            raise GatewayError("BUSY", "当前回合尚未收尾，请等待完成或取消。", 409, True)

    @staticmethod
    def _duplicate(conversation, request_id, kind, payload):
        previous = conversation.commands.get(request_id)
        if previous is None:
            return None
        if previous["kind"] != kind or previous["payload"] != payload:
            raise GatewayError("REQUEST_CONFLICT", "同一请求编号不能用于不同操作或内容。")
        return dict(deepcopy(previous["response"]), replayed=True)

    @staticmethod
    def _save(conversation, request_id, kind, payload, response):
        conversation.commands[request_id] = {
            "kind": kind, "payload": payload, "response": deepcopy(response),
        }

    def status(self):
        with self.lock:
            ready = bool(not self.stopping and self.engine and self.engine.healthy)
            failure = self.failure
            if not ready and self.engine is not None and not self.stopping and failure is None:
                failure = GatewayError("BACKEND_UNAVAILABLE", "模型不可用，需要重启服务后再试。", 503)
            return {"schema_version": "ui.v1", "instance_id": self.journal.instance_id,
                    "phase": self.phase, "ready": ready, "busy": self.work is not None,
                    "current_session_id": self.current_session,
                    "backend": {"configured": self.backend_name,
                                "execution_kind": (self.engine.execution_kind if self.engine else
                                    "DEMO_RULE" if self.backend_name == "demo" else
                                    "CPU_REFERENCE" if self.backend_name == "native" else None),
                                "ready": ready, "hardware_enabled": bool(ready and self.engine
                                    and self.engine.execution_kind == "FPGA_REAL")},
                    "capabilities": {"text": True, "audio": False, "rule_score": True,
                                     "chief_narration": True, "chief_summary_kind": "RULE_TEMPLATE",
                                     "cancel_turn": bool(self.engine and self.engine.can_cancel),
                                     "generation_timeout_s": self.engine.generation_timeout_s if self.engine else None,
                                     "max_active_turns": 1,
                                     "pending_turn_queue": 0, "max_turns": 200, "max_sessions": 8},
                    "failure": None if failure is None else
                    {"code": failure.code, "message": failure.message},
                    "verification": {"software_test_only": True, "board": "NOT_TESTED",
                                     "medical_review": "PENDING_TEACHER_REVIEW"}}

    def cases(self):
        with self.lock:
            self._require_ready()
            return self.engine.cases()

    def create_session(self, request_id, case_id):
        with self.lock:
            if request_id in self.starts:
                previous = self.starts[request_id]
                if previous["case_id"] != case_id:
                    raise GatewayError("REQUEST_CONFLICT", "开始请求编号已用于其他病例。")
                return dict(deepcopy(previous["response"]), replayed=True)
            self._require_ready()
            self._idle()
            if self.current_session and not self.conversations[self.current_session].closed:
                raise GatewayError("SESSION_ACTIVE", "请先结束当前问诊，再开始新问诊。")
            if len(self.conversations) >= 8:
                raise GatewayError("SESSION_LIMIT", "本次服务的会话容量已满，请保存记录后重启。", 409)
            business = self.engine.new_session(case_id)
            session_id = business.snapshot()["session_id"]
            self.conversations[session_id] = Conversation(business)
            self.current_session = session_id
            self.phase = "READY"
            response = {"session_id": session_id, "case_id": case_id, "epoch": 0,
                        "status": "created", "replayed": False}
            self.starts[request_id] = {"case_id": case_id, "response": response}
            self.journal.emit("session.created", session_id, request_id, 0, case_id=case_id)
            return deepcopy(response)

    def snapshot(self, session_id):
        with self.lock:
            conversation = self._conversation(session_id)
            identity = conversation.business.snapshot()
            active = self.work if self.work and self.work.session_id == session_id else None
            return {"schema_version": "ui.v1", "instance_id": self.journal.instance_id,
                    "cursor": self.journal.sequence, "session_id": session_id,
                    "case_id": identity["case_id"], "case_version": identity["case_version"],
                    "epoch": conversation.epoch, "closed": conversation.closed,
                    "phase": "FINISHED" if conversation.closed else self.phase,
                    "active_request_id": active.request_id if active else None,
                    "operation_id": active.operation_id if active else None,
                    "turns": deepcopy(conversation.turns),
                    "evaluation_ready": conversation.evaluation is not None}

    def submit(self, session_id, request_id, text):
        with self.lock:
            conversation = self._conversation(session_id)
            previous = self._duplicate(conversation, request_id, "turn", text)
            if previous:
                return previous
            if conversation.closed:
                raise GatewayError("SESSION_CLOSED", "该问诊已经结束。")
            self._require_ready()
            self._idle()
            if len(conversation.turns) >= 200:
                raise GatewayError("TURN_LIMIT", "该问诊已达到 200 轮上限。")
            work = Work(session_id, request_id, conversation.epoch)
            self.work = work
            self.phase = "PROCESSING"
            conversation.turns.append({"request_id": request_id, "operation_id": work.operation_id,
                                       "question": text, "status": "RUNNING", "answer": None,
                                       "answer_source": None, "actual_backend": None,
                                       "delivery_kind": None, "delivery_receipt": None, "error": None})
            response = {"status": "accepted", "session_id": session_id, "request_id": request_id,
                        "operation_id": work.operation_id, "epoch": work.epoch, "replayed": False}
            self._save(conversation, request_id, "turn", text, response)
            self.journal.emit("turn.accepted", session_id, request_id, work.epoch,
                              operation_id=work.operation_id)
            # Reservation is made under the same lock before submitting: no hidden waiting turns.
            self.executor.submit(self._run_turn, work, text)
            return response

    def turn_result(self, session_id, request_id):
        with self.lock:
            conversation = self._conversation(session_id)
            for turn in conversation.turns:
                if turn["request_id"] == request_id:
                    return deepcopy(turn)
            raise GatewayError("TURN_NOT_FOUND", "该会话中没有这个提问请求。", 404)

    def _stage(self, work, name):
        with self.lock:
            conversation = self.conversations[work.session_id]
            if work.cancelled.is_set() or work.epoch != conversation.epoch:
                return
            self.phase = {"generation.started": "GENERATING", "validation.started": "VALIDATING",
                          "response.preparing": "PROCESSING"}[name]
            self.journal.emit(name, work.session_id, work.request_id, work.epoch)

    def _run_turn(self, work, text):
        conversation = self.conversations[work.session_id]
        outcome = "COMPLETED"
        public_error = None
        answer = None
        try:
            if work.cancelled.is_set():
                raise OperationCancelled()
            answer = self.engine.answer(conversation.business, work.request_id, text,
                                        lambda name: self._stage(work, name), work.cancelled, work.epoch)
        except OperationCancelled:
            outcome = "CANCELLED"
        except Exception as error:
            LOG.exception("Turn failed: %s", work.request_id)
            public_error = error if isinstance(error, GatewayError) else GatewayError(
                "TURN_FAILED", "本轮处理失败，未发布回答。", 503)
            outcome = "FAILED"
        # Cancellation and publication share this lock: no late result can slip into history.
        with self.lock:
            turn = conversation.turns[-1]
            if work.cancelled.is_set() or work.epoch != conversation.epoch:
                outcome = "CANCELLED"
                public_error = None
            if outcome == "COMPLETED":
                try:
                    receipt = conversation.business.publish_text(
                        work.request_id, conversation.business.epoch, answer,
                        instance_id=self.journal.instance_id, operation_id=work.operation_id,
                        request_epoch=work.epoch,
                    )
                except Exception:
                    LOG.exception("Text publication failed")
                    outcome = "FAILED"
                    public_error = GatewayError("PUBLICATION_FAILED", "回答交付失败，未写入历史。", 503)
                else:
                    turn.update(answer=answer.text, answer_source=answer.source,
                                actual_backend=answer.actual_backend, delivery_kind="WEB_TEXT_PUBLISHED",
                                delivery_receipt=receipt)
                    self.journal.emit("answer.ready", work.session_id, work.request_id, work.epoch,
                                      text=answer.text, answer_source=answer.source,
                                      actual_backend=answer.actual_backend, delivery_kind="WEB_TEXT_PUBLISHED",
                                      delivery_receipt=deepcopy(receipt))
            if outcome != "COMPLETED":
                conversation.business.cancel()
            turn["status"] = outcome
            if public_error:
                turn["error"] = {"code": public_error.code, "message": public_error.message}
            self.work = None
            self.phase = "READY" if self.engine.healthy else "FAILED"
            self.journal.emit({"COMPLETED": "turn.completed", "CANCELLED": "turn.cancelled",
                               "FAILED": "turn.failed"}[outcome],
                              work.session_id, work.request_id, conversation.epoch,
                              status=outcome, ready=self.engine.healthy, error=turn["error"])

    def cancel(self, session_id, request_id, target_request_id):
        with self.lock:
            conversation = self._conversation(session_id)
            if self.engine and not self.engine.can_cancel:
                raise GatewayError("CANCEL_UNAVAILABLE", "本次板端演示请等待回答完成。", 409)
            previous = self._duplicate(conversation, request_id, "cancel", target_request_id)
            if previous:
                return previous
            if len(conversation.commands) >= 601:
                raise GatewayError("COMMAND_LIMIT", "会话操作数量已达上限。")
            work = self.work
            if not work or work.session_id != session_id or work.request_id != target_request_id:
                raise GatewayError("NO_MATCHING_OPERATION", "该请求已结束，或不是当前活动请求。")
            if not work.cancelled.is_set():
                conversation.epoch += 1
                work.cancelled.set()
                self.phase = "CANCELLING"
                self.journal.emit("cancel.pending", session_id, target_request_id,
                                  conversation.epoch, command_request_id=request_id)
                # Non-blocking request only; the worker owns cleanup and the final event.
                try:
                    self.engine.cancel()
                except Exception:
                    LOG.exception("Backend cancel signal failed; epoch still invalidated")
            response = {"status": "cancel_pending", "session_id": session_id,
                        "request_id": request_id, "target_request_id": target_request_id,
                        "epoch": conversation.epoch, "replayed": False}
            self._save(conversation, request_id, "cancel", target_request_id, response)
            return response

    def finish(self, session_id, request_id):
        with self.lock:
            conversation = self._conversation(session_id)
            previous = self._duplicate(conversation, request_id, "finish", None)
            if previous:
                return previous
            if conversation.closed:
                # Closing is idempotent even under a new retry ID; don't grow a closed session.
                return {"status": "finished", "session_id": session_id, "replayed": True}
            self._idle()
            if not conversation.closed:
                # Prepare the frozen view before committing close; failed formatting leaves the session open.
                frozen = conversation.business.snapshot()
                frozen["closed"] = True
                evaluation = build_evaluation(
                    instance_id=self.journal.instance_id,
                    business_snapshot=frozen, turns=conversation.turns,
                    rule_score=conversation.business.recompute_score_for_host(),
                )
                conversation.business.finish()
                conversation.evaluation = evaluation
                conversation.closed = True
                self.phase = "FINISHED"
                self.journal.emit("session.finished", session_id, request_id, conversation.epoch)
                self.journal.emit("evaluation.ready", session_id, request_id, conversation.epoch,
                                  evaluation_id=evaluation["evaluation_id"], summary_source="RULE_TEMPLATE")
            response = {"status": "finished", "session_id": session_id, "replayed": False}
            self._save(conversation, request_id, "finish", None, response)
            return response

    def evaluation(self, session_id):
        with self.lock:
            conversation = self._conversation(session_id)
            if not conversation.closed:
                raise GatewayError("SESSION_NOT_FINISHED", "请先结束问诊再查看结果。")
            return deepcopy(conversation.evaluation)

    def event_batch(self, session_id, after):
        with self.lock:
            self._conversation(session_id)
            return self.journal.read(after, session_id)

    def close(self):
        with self.lock:
            if self.stopping:
                return
            self.stopping = True
            self.phase = "STOPPING"
            if self.work:
                self.work.cancelled.set()
                self.conversations[self.work.session_id].epoch += 1
                if self.engine:
                    self.engine.cancel()
        self.executor.shutdown(wait=True)
        if self.engine:
            self.engine.close()

