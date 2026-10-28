"""Dispatch checks with synthetic engines; this file does not run a model or PL."""

import time

from fastapi.testclient import TestClient

from patient_web.api import create_app
from patient_web.engine import TextEngine


class SyntheticCPU(TextEngine):
    def __init__(self):
        super().__init__("demo")
        self.backend = "native"
        self.execution_kind = "CPU_REFERENCE"
        self.can_cancel = False

    @property
    def healthy(self):
        return True

    def close(self):
        pass


def wait_for(client, condition):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(.01)
    raise AssertionError("Normal operation did not complete")


def test_switch_between_completed_turns_keeps_actual_delivery_provenance():
    options = {"demo": {"label": "规则演示", "factory": lambda: TextEngine("demo")},
               "native": {"label": "CPU", "factory": SyntheticCPU}}
    app = create_app(backend="demo", backend_options=options)
    with TestClient(app) as client:
        assert app.state.coordinator.initialized.wait(3)
        start = client.post("/ui/v1/sessions", json={"request_id": "start", "case_id": "SYN_CP_01"}).json()
        path = "/ui/v1/sessions/" + start["session_id"]
        client.post(path + "/turns", json={"request_id": "one", "text": "哪里疼？"}).raise_for_status()
        wait_for(client, lambda: not client.get(path).json()["active_request_id"])
        response = client.post("/ui/v1/backend", json={"request_id": "cpu", "backend": "native"})
        assert response.status_code == 202
        wait_for(client, lambda: client.get("/ui/v1/status").json()["ready"])
        assert client.get("/ui/v1/status").json()["backend"]["execution_kind"] == "CPU_REFERENCE"
        client.post(path + "/turns", json={"request_id": "two", "text": "每次疼痛持续多久？"}).raise_for_status()
        wait_for(client, lambda: not client.get(path).json()["active_request_id"])
        turns = client.get(path).json()["turns"]
        assert turns[0]["answer_source"] == "DEMO_RULE"
        assert turns[0]["delivery_receipt"]["actual_backend"] is None
        assert turns[1]["answer_source"] == "MODEL"
        assert turns[1]["delivery_receipt"]["actual_backend"] == "CPU_REFERENCE"
        client.post("/ui/v1/backend", json={"request_id": "back", "backend": "demo"}).raise_for_status()
        wait_for(client, lambda: client.get("/ui/v1/status").json()["ready"])
        client.post(path + "/finish", json={"request_id": "finish"}).raise_for_status()
        assert client.get(path + "/evaluation").json()["rule_score"]["score"] == 20
