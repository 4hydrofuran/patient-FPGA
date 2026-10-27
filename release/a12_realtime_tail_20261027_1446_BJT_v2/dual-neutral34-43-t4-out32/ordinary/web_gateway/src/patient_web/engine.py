"""Text-only use of A02 Session and A05's native adapter; never starts voice workers."""

from copy import deepcopy
from dataclasses import dataclass
import importlib
import math
import os
from pathlib import Path
import signal
import sys
import threading
import time

from .delivery import DeliveryReceipt, text_hash
from .errors import GatewayError, OperationCancelled
from .reference.domain import digest, load_case
from .reference.session import Session, exclusive

CASE_IDS = ("SYN_CP_01", "SYN_CP_02", "SYN_CP_03")


class PublishedSession(Session):
    """A new explicit delivery kind, independent of the old PC_TEXT_TEST_ACK."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text_receipts = {}

    @exclusive
    def publish_text(self, request_id: str, epoch: int, answer, *, instance_id: str,
                     operation_id: str, request_epoch: int):
        if self._closed or epoch != self._epoch:
            raise RuntimeError("Closed session or stale text publication")
        previous = self._text_receipts.get(request_id)
        if previous is not None:
            prior_epoch, receipt = previous
            if (prior_epoch != epoch or receipt["answer_sha256"] != text_hash(answer.text)
                    or receipt["answer_source"] != answer.source
                    or receipt["actual_backend"] != answer.actual_backend
                    or receipt["instance_id"] != instance_id
                    or receipt["operation_id"] != operation_id or receipt["epoch"] != request_epoch):
                raise RuntimeError("Conflicting publication retry")
            return deepcopy(receipt)
        pending = self._pending
        if not pending or pending["request_id"] != request_id or pending["epoch"] != epoch:
            raise RuntimeError("Stale text publication")
        response = self._received[request_id]["response"]
        # The adapter-returned text must be the exact text approved by the business checker.
        if (response.get("final_check", {}).get("status") != "pass"
                or not response.get("tts_ready") or response.get("text") != answer.text
                or pending["text"] != answer.text or pending["text_sha256"] != digest(answer.text)
                or response.get("answer_source") != answer.source
                or response.get("cache_provenance") != answer.cache_provenance):
            raise RuntimeError("Publication differs from checked answer")
        receipt = DeliveryReceipt(
            schema_version="text-delivery.v2" if answer.source == "MODEL_CACHE" else "text-delivery.v1",
            instance_id=instance_id, session_id=self._id, request_id=request_id,
            operation_id=operation_id, epoch=request_epoch, case_id=self._case.case_id,
            case_version=self._case.version, case_sha256=self._case.sha256,
            answer_sha256=text_hash(answer.text), answer_source=answer.source,
            actual_backend=answer.actual_backend, model_called=bool(response["llm_calls"]),
            cache_provenance=deepcopy(answer.cache_provenance),
            validated_monotonic_ns=str(response["validated_ns"]),
            published_monotonic_ns=str(time.monotonic_ns()),
        ).model_dump()
        # All checks and receipt construction precede this single history commit.
        self._played.append(dict(pending, delivery_kind="WEB_TEXT_PUBLISHED", audio_played=False,
                                 delivery_receipt=deepcopy(receipt)))
        self._text_receipts[request_id] = (epoch, receipt)
        self._pending = None
        return deepcopy(receipt)

    def mark_demo(self, request_id, response):
        # Session's original MODEL label must never survive a rules-only demonstration.
        if response.get("answer_source") == "MODEL":
            response["answer_source"] = "DEMO_RULE"
        elif response.get("answer_source") == "TIMEOUT":
            # A simulated deadline still publishes a checked template, never a
            # receipt claiming that a real model timed out. Lab diagnostics retain the injection.
            response["answer_source"] = "TEMPLATE"
        # Also correct counts when a demo candidate was rejected or timed out in a test.
        response.update(llm_calls=0, model_result=None)
        self._received[request_id]["response"] = deepcopy(response)
        return response


@dataclass(frozen=True)
class CheckedAnswer:
    text: str
    source: str
    actual_backend: str | None
    cache_provenance: dict | None = None


class RulesModel:
    """Explicit demonstration only: repeat the requested approved expressions, no LLM."""

    def generate(self, messages, timeout_s=20):
        marker = "本轮已核对的事实句（逐句原样说出）：\n"
        expressions = messages[-1]["content"].split(marker, 1)[1]
        return {"text": "".join(expressions.splitlines()), "status": "OK", "eos": True}


class ObservedModel:
    def __init__(self, model, emit, cancelled, demo):
        self.model, self.emit, self.cancelled, self.demo = model, emit, cancelled, demo

    def generate(self, messages, timeout_s=20):
        if self.cancelled.is_set():
            raise RuntimeError("Operation cancelled before generation")
        self.emit("response.preparing" if self.demo else "generation.started")
        try:
            result = self.model.generate(messages, timeout_s=timeout_s)
        except TimeoutError:
            # Session checks its explicit timeout fallback after catching this exception.
            self.emit("validation.started")
            raise
        # No validation event on backend/protocol failure: Session returns an error directly.
        self.emit("validation.started")
        return result


class TextEngine:
    def __init__(self, backend="native", project_root=None, output=None, threads=3,
                 generation_timeout_s=180):
        if (type(generation_timeout_s) not in (int, float)
                or not math.isfinite(generation_timeout_s) or not 1 <= generation_timeout_s <= 600):
            raise ValueError("generation timeout must be 1..600 seconds")
        self.backend = backend
        self.generation_timeout_s = generation_timeout_s
        self.execution_kind = "DEMO_RULE" if backend == "demo" else "CPU_REFERENCE"
        self.can_cancel = True
        self.model = None
        self.prepare = None
        self.init_failed = False
        self.process_lock = threading.Lock()
        if backend == "demo":
            self.model = RulesModel()
            return
        if backend != "native":
            raise ValueError("Unknown backend")
        if os.name != "posix":
            raise GatewayError("NATIVE_REQUIRES_LINUX", "真实模型适配器需要 Linux／WSL 环境。", 503)
        if project_root is None or output is None:
            raise GatewayError("MODEL_NOT_CONFIGURED", "尚未指定 A 侧工程与运行记录目录。", 503)
        root = Path(project_root).resolve()
        required = ("system_qwen35/app/native_w4a8.py", "system_qwen35/app/default_e2e/prompts.py",
                    "modules/linear_A/manifest.a09.json")
        if any(not (root / name).is_file() for name in required):
            raise GatewayError("MODEL_ASSETS_MISSING", "A 侧真实模型工程或封存清单不完整。", 503)
        # Only a trusted startup argument chooses this root; no HTTP request chooses code paths.
        sys.path.insert(0, str(root))
        module = importlib.import_module("system_qwen35.app.native_w4a8")
        if not Path(module.__file__).resolve().is_relative_to(root):
            raise RuntimeError("Conflicting upstream module already imported")
        self.prepare = importlib.import_module("system_qwen35.app.default_e2e.prompts").prepare
        thread_env = {name: "1" for name in
                      ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
        self.model = module.NativeW4A8(
            Path(output), threads=threads, kernel_threads=threads,
            thread_env=thread_env, manifest_path="modules/linear_A/manifest.a09.json",
        )

    @property
    def healthy(self):
        with self.process_lock:
            model = self.model
            if model is None or self.init_failed:
                return False
            return self.backend == "demo" or (not model.broken and model.p.poll() is None)

    def cases(self):
        return [{"case_id": case_id, "title": f"合成胸痛病例 {index}",
                 "case_version": load_case(case_id).version,
                 "review_status": "PENDING_TEACHER_REVIEW", "software_test_only": True}
                for index, case_id in enumerate(CASE_IDS, 1)]

    def new_session(self, case_id):
        if case_id not in CASE_IDS:
            raise GatewayError("CASE_NOT_FOUND", "该病例不存在。", 404)
        return PublishedSession(case_id, software_test=True,
                                prompt_builder=getattr(self, 'prompt_builder', None),
                                answer_cache=getattr(self, 'answer_cache', None))

    def answer(self, session, request_id, text, emit, cancelled, epoch, timeout_s=None):
        owner = self
        timeout_s = self.generation_timeout_s if timeout_s is None else timeout_s

        class PreparedModel:
            def generate(self, messages, timeout_s=20):
                if owner.prepare is not None:
                    messages, _ = owner.prepare(messages, "facts_v4")
                if owner.backend != "demo":
                    owner.model.trace_context = {
                        "session_id": session.snapshot()["session_id"],
                        "request_id": request_id, "epoch": epoch,
                    }
                try:
                    result = owner.model.generate(messages, timeout_s=timeout_s)
                except (TimeoutError, RuntimeError):
                    if owner.backend != "demo":
                        owner.model.broken = True
                    raise
                if (not isinstance(result, dict) or type(result.get("eos")) is not bool
                        or not isinstance(result.get("text"), str)
                        or result.get("status") not in ("OK", "CANCELLED", "ERROR", "TIMEOUT")):
                    if owner.backend != "demo":
                        owner.model.broken = True
                    raise RuntimeError("Invalid model result envelope")
                if result.get("actual_backend") not in (None, owner.execution_kind):
                    if owner.backend != "demo":
                        owner.model.broken = True
                    raise RuntimeError("Unexpected actual model backend")
                expected_id = session.snapshot()["session_id"] + ":" + request_id
                if "id" in result and result["id"] != expected_id:
                    if owner.backend != "demo":
                        owner.model.broken = True
                    raise RuntimeError("Foreign model result identity")
                if result["status"] == "CANCELLED":
                    raise OperationCancelled()
                if result["status"] in ("ERROR", "TIMEOUT"):
                    if owner.backend != "demo":
                        owner.model.broken = True
                    if result["status"] == "TIMEOUT":
                        raise TimeoutError("Native worker returned TIMEOUT")
                    raise RuntimeError("Native worker returned ERROR")
                return result

        observed = ObservedModel(PreparedModel(), emit, cancelled, self.backend == "demo")
        try:
            result = session.submit({"request_id": request_id, "text": text,
                                     "source": "typed", "final": True},
                                    observed, timeout_s=timeout_s)
        finally:
            if self.backend != "demo":
                self.model.trace_context = None
        if cancelled.is_set():
            raise OperationCancelled()
        if result.get("type") == "error":
            raise GatewayError("MODEL_ERROR", "回答模块处理失败；本轮没有发布回答。", 503)
        if not result.get("tts_ready") or result.get("final_check", {}).get("status") != "pass":
            raise GatewayError("ANSWER_NOT_APPROVED", "回答未通过检查，未予展示。", 503)
        if self.backend == "demo":
            result = session.mark_demo(request_id, result)
        actual = self.execution_kind if self.backend != "demo" and result.get("llm_calls") else None
        return CheckedAnswer(result["text"], result["answer_source"], actual,result.get('cache_provenance'))

    def cancel(self):
        with self.process_lock:
            model = self.model
            if self.backend == "native" and model is not None and model.p.poll() is None:
                model.p.send_signal(signal.SIGUSR1)

    def close(self):
        if self.backend == "native" and self.model is not None:
            self.model.close()

