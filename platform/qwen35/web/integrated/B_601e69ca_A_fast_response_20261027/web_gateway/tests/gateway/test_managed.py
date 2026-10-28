"""Normal path against frozen A12 NativePL + a transport fixture, not a model/PL run."""

from contextlib import contextmanager
import json
from pathlib import Path
import sys
import types

from fastapi.testclient import TestClient
import uvicorn
import socket
import threading
import time

from patient_web.acceptance import run_probe
from patient_web.managed import create_managed_app


class TransportFixture:
    def __init__(self):
        self.requests = []
        self.timeouts = []
        self.closed = False

    def send(self, request):
        self.requests.append(request)

    def get(self, timeout):
        self.timeouts.append(timeout)
        return {"type": "result", "id": self.requests[-1]["id"], "status": "OK",
                "text": "每次疼痛持续10分钟。", "eos": True, "partial_output_usable": True,
                "state_cleared_before_response": True, "state_position_after_clear": -1,
                "bridge": {"a12_route": {"execution_kind": "FPGA_REAL"}}}

    def close(self):
        self.closed = True
        return True


def reference_model(tmp_path, monkeypatch):
    # Run the actual frozen NativePL Python class; only worker responses are synthetic.
    package = types.ModuleType("ps_reference")
    package.__path__ = []
    native = types.ModuleType("ps_reference.native")
    native.ROOT = tmp_path
    module = types.ModuleType("ps_reference.native_pl")
    module.__package__ = "ps_reference"
    monkeypatch.setitem(sys.modules, "ps_reference", package)
    monkeypatch.setitem(sys.modules, "ps_reference.native", native)
    source = Path(__file__).with_name("native_pl_reference.txt").read_text(encoding="utf-8")
    exec(compile(source, "frozen_A12_native_pl.py", "exec"), module.__dict__)
    template = tmp_path / "artifacts/qwen35-0.8b/source/chat_template.jinja"
    template.parent.mkdir(parents=True)
    template.write_text('{{ messages[1]["content"] }}<think>{{ "\\n\\n" }}</think>{{ "\\n\\n" }}', encoding="utf-8")
    ready = {"type": "ready", "execution_kind": "FPGA_REAL", "physical_ubatch": 8,
             "cache_policy": "R0_CLEAR_ALL_REPLAY",
             "attention_schedule": "SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING",
             "non_mlp_projection_schedule": "STABLE_PER_TOKEN_SIMD_GEMV",
             "bridge": {"a12_route": {"a12_route_scope": "all",
                        "contract_sha256": "83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6"}}}
    return module.NativePL(TransportFixture(), ready, max_output_tokens=32)


def test_managed_normal_delivery_and_chief_feedback(tmp_path, monkeypatch):
    model = reference_model(tmp_path, monkeypatch)
    app = create_managed_app(model, is_ready=lambda: True, generation_timeout_s=180)
    with TestClient(app) as client:
        assert app.state.coordinator.initialized.wait(3)
        status = client.get("/ui/v1/status").json()
        assert status["backend"]["execution_kind"] == "FPGA_REAL"
        assert status["capabilities"]["generation_timeout_s"] == 180
        assert status["capabilities"]["cancel_turn"] is False
        start = client.post("/ui/v1/sessions", json={"request_id": "start", "case_id": "SYN_CP_01"}).json()
        path = "/ui/v1/sessions/" + start["session_id"]
        assert client.post(path + "/turns", json={"request_id": "question", "text": "每次疼痛持续多久？"}).status_code == 202
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            state = client.get(path).json()
            if not state["active_request_id"]:
                break
            time.sleep(.01)
        turn = state["turns"][0]
        assert turn["status"] == "COMPLETED" and turn["answer_source"] == "MODEL"
        assert turn["delivery_receipt"]["actual_backend"] == "FPGA_REAL"
        assert turn["delivery_receipt"]["model_called"] is True
        assert client.post(path + "/finish", json={"request_id": "finish"}).status_code == 200
        evaluation = client.get(path + "/evaluation").json()
        assert evaluation["rule_score"]["score"] == 10 and evaluation["summary_source"] == "RULE_TEMPLATE"
        assert len(model.worker.requests) == 1 and model.worker.requests[0]["id"] == "a12-1"
        assert model.worker.requests[0]["session_id"] == start["session_id"]
        assert model.worker.requests[0]["cache_policy"] == "R0"
        assert 179 < model.worker.timeouts[0] <= 180
        assert model.trace_context is None
    assert model.worker.closed is False  # Native ownership stays with the PS manager.


def test_single_demo_http_probe_uses_one_model_request_only(tmp_path, monkeypatch):
    model = reference_model(tmp_path, monkeypatch)
    app = create_managed_app(model, is_ready=lambda: True)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    instance = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=lambda: instance.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 3
        while not instance.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert instance.started and app.state.coordinator.initialized.wait(3)
        report = run_probe(origin, "managed-pl", timeout_s=3, single_demo=True)
        assert report["verdict"] == "PASS_MANAGED_PL_TEXT_DELIVERY", report.get("failure")
        assert len(model.worker.requests) == 1
        assert report["evaluation"]["rule_score"]["score"] == 10
        assert not any("cancel" in check or "retry" in check for check in report["checks"])
        # Export clear test-domain metadata; never label this fixture as a board result.
        report["validation_kind"] = "PC_NATIVEPL_PROTOCOL_FIXTURE_NOT_MODEL_OR_BOARD"
        output = Path(__file__).resolve().parents[2] / "runtime/minimal-managed-smoke.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        instance.should_exit = True
        thread.join(5)
        sock.close()
        assert not thread.is_alive()
    assert model.worker.closed is False
