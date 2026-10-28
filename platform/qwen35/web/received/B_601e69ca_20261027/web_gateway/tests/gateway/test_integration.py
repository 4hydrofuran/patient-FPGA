"""Native adapter wiring uses a fixture, never represented as actual model validation."""

import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

from patient_web import engine as engine_module
from patient_web.engine import TextEngine


def test_native_adapter_uses_selected_manifest_prompt_and_correlation(tmp_path, monkeypatch):
    root = tmp_path / "upstream"
    sources = {
        "system_qwen35/__init__.py":"",
        "system_qwen35/app/__init__.py":"",
        "system_qwen35/app/default_e2e/__init__.py":"",
        "system_qwen35/app/default_e2e/prompts.py":
            "def prepare(messages, style):\n    assert style == 'facts_v4'\n    return messages, {}\n",
        "modules/linear_A/manifest.a09.json":"{}",
        "system_qwen35/app/native_w4a8.py": '''
class Process:
    def __init__(self): self.signals=[]
    def poll(self): return None
    def send_signal(self, signal): self.signals.append(signal)
class NativeW4A8:
    def __init__(self, output, **kwargs):
        self.output=output;self.options=kwargs;self.p=Process();self.broken=False;self.closed=False
    def generate(self, messages, timeout_s=20):
        self.received_context=dict(self.trace_context)
        return {'text':'每次疼痛持续10分钟。','status':'OK','eos':True}
    def close(self): self.closed=True
''',
    }
    for name, contents in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(engine_module, "os", SimpleNamespace(name="posix", environ=os.environ))
    monkeypatch.setattr(engine_module, "signal", SimpleNamespace(SIGUSR1=101))
    prior_path = list(sys.path)
    prior_modules = {key:value for key,value in sys.modules.items() if key.startswith("system_qwen35")}
    try:
        for key in prior_modules:
            del sys.modules[key]
        native = TextEngine("native", root, tmp_path/"output", threads=3)
        session = native.new_session("SYN_CP_01")
        events = []
        answer = native.answer(session,"question", "每次疼痛持续多久？", events.append,
                               threading.Event(), epoch=7)
        assert native.model.options["manifest_path"] == "modules/linear_A/manifest.a09.json"
        assert native.model.options["threads"] == native.model.options["kernel_threads"] == 3
        assert native.model.received_context == {"session_id":session.snapshot()["session_id"],
                                                 "request_id":"question", "epoch":7}
        assert events == ["generation.started", "validation.started"]
        assert answer.text == "每次疼痛持续10分钟。" and answer.source == "MODEL"
        assert native.model.trace_context is None
        native.cancel()
        assert native.model.p.signals == [101]
        native.model.broken = True
        assert native.healthy is False
        native.close()
        assert native.model.closed
    finally:
        sys.path[:] = prior_path
        for key in list(sys.modules):
            if key.startswith("system_qwen35"):
                del sys.modules[key]
        sys.modules.update(prior_modules)


def test_demo_answer_is_relabelled_in_cached_business_response():
    demo = TextEngine("demo")
    session = demo.new_session("SYN_CP_01")
    answer = demo.answer(session,"q", "哪里疼？", lambda event:None, threading.Event(), epoch=0)
    cached = session._received["q"]["response"]
    assert answer.source == cached["answer_source"] == "DEMO_RULE"
    assert cached["llm_calls"] == 0 and cached["model_result"] is None


def test_incorrect_candidate_never_leaves_fact_check_gate():
    demo = TextEngine("demo")
    demo.model.generate = lambda *args,**kwargs: {"text":"每次疼痛持续99分钟。", "status":"OK", "eos":True}
    session = demo.new_session("SYN_CP_01")
    answer = demo.answer(session,"q", "每次疼痛持续多久？", lambda event:None, threading.Event(), epoch=0)
    assert answer.text == "每次疼痛持续10分钟。" and answer.source == "TEMPLATE"

