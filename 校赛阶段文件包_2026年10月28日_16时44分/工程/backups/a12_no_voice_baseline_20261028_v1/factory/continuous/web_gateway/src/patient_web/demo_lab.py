"""Opt-in, bounded fault simulation. No model, audio, or hardware is executed."""

from contextlib import contextmanager
from copy import deepcopy
import threading

from .engine import RulesModel, TextEngine

SCENARIOS = {
    "normal": "正常规则回答",
    "delayed": "延迟返回（可测试取消）",
    "wrong_fact": "错误事实候选（应被拦截）",
    "timeout": "模拟回答超时",
    "failure": "模拟回答失败",
}


class ScriptedRules(RulesModel):
    def __init__(self):
        self.lock = threading.RLock()
        self.shutdown = threading.Event()
        self.pending = {"scenario": "normal", "delay_s": 3.0}
        self.active = None
        self.history = []

    def arm(self, scenario, delay_s):
        with self.lock:
            self.pending = {"scenario": scenario, "delay_s": delay_s}
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            return deepcopy({"enabled": True, "software_test_only": True,
                             "model_called": False, "scenarios": SCENARIOS,
                             "pending": self.pending, "active": self.active,
                             "history": self.history})

    @contextmanager
    def turn(self, request_id):
        with self.lock:
            self.active = dict(self.pending, request_id=request_id, adapter_invoked=False,
                               injection=None, outcome="RUNNING")
            self.pending = {"scenario": "normal", "delay_s": 3.0}
        try:
            yield
        except BaseException:
            with self.lock:
                self.active["outcome"] = "NO_CHECKED_RESULT"
            raise
        else:
            with self.lock:
                self.active["outcome"] = "CHECKED_RESULT_RETURNED"
        finally:
            with self.lock:
                self.history.append(self.active)
                self.history = self.history[-20:]
                self.active = None

    def generate(self, messages, timeout_s=20):
        with self.lock:
            scenario = self.active["scenario"]
            delay = self.active["delay_s"]
            self.active["adapter_invoked"] = True
        # Deliberately ignore turn cancellation: exercise the real stale-result gate.
        # Service shutdown may shorten the bounded wait so stopping never hangs.
        if scenario in ("delayed", "timeout", "failure"):
            self.shutdown.wait(delay)
        with self.lock:
            self.active["injection"] = scenario
        if scenario == "timeout":
            raise TimeoutError("Explicit demo-lab timeout")
        if scenario == "failure":
            return {"text": "", "status": "ERROR", "eos": True}
        if scenario == "wrong_fact":
            return {"text": "每次疼痛持续99分钟。", "status": "OK", "eos": True}
        return super().generate(messages, timeout_s)


class LabEngine(TextEngine):
    def __init__(self):
        super().__init__("demo")
        self.model = ScriptedRules()

    def answer(self, session, request_id, *args, **kwargs):
        # One accepted turn consumes one selection, including template-only questions.
        with self.model.turn(request_id):
            return super().answer(session, request_id, *args, **kwargs)

    def close(self):
        self.model.shutdown.set()

    def cancel(self):
        # Do not accelerate simulated cancellation; a late result must be discarded.
        pass
