"""Publication contract: checked bytes, receipts, late answers, and truthful provenance."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import threading

from fastapi.testclient import TestClient
import pytest

from patient_web.api import create_app
from patient_web.delivery import DeliveryReceipt, TurnResult
from patient_web.engine import TextEngine
from test_commands import begin, running, settled, submit
from test_events import complete, events_until, server


def prepared():
    engine = TextEngine("demo")
    session = engine.new_session("SYN_CP_01")
    answer = engine.answer(session, "q", "每次疼痛持续多久？", lambda event:None,
                           threading.Event(), epoch=0)
    return session, answer


def publish(session, answer, **overrides):
    options = {"instance_id":"instance", "operation_id":"operation", "request_epoch":0}
    options.update(overrides)
    return session.publish_text("q", session.epoch, answer, **options)


def test_receipt_matches_result_snapshot_and_replay_without_double_history():
    with running() as (client, engine, manager):
        sid = begin(client)
        first = submit(client, sid).json()
        snapshot = settled(client, sid)
        result = client.get(f"/ui/v1/sessions/{sid}/turns/question").json()
        TurnResult.model_validate(result)
        receipt = DeliveryReceipt.model_validate(result["delivery_receipt"])
        assert receipt.answer_sha256 == hashlib.sha256(result["answer"].encode("utf-8")).hexdigest()
        assert receipt.session_id == sid and receipt.operation_id == first["operation_id"]
        assert receipt.validation_status == "pass" and receipt.model_called is False
        assert not receipt.audio_played and not receipt.browser_render_verified and not receipt.user_read_verified
        assert snapshot["turns"][0] == result
        submit(client, sid)
        assert client.get(f"/ui/v1/sessions/{sid}/turns/question").json() == result
        assert engine.calls == 1
        assert len(manager.conversations[sid].business.snapshot()["played"]) == 1
        assert client.get(f"/ui/v1/sessions/{sid}/turns/other").status_code == 404


@pytest.mark.parametrize("change", [
    {"text":"每次疼痛持续99分钟。"}, {"source":"MODEL"}, {"actual_backend":"CPU_REFERENCE"},
])
def test_modified_text_or_provenance_cannot_be_published(change):
    session, answer = prepared()
    with pytest.raises((RuntimeError, ValueError)):
        publish(session, replace(answer, **change))
    assert session.snapshot()["played"] == []
    # An invalid attempt did not consume the approved pending answer.
    assert publish(session, answer)["answer_source"] == "DEMO_RULE"


def test_low_level_publication_retry_is_idempotent_and_conflicts_are_rejected():
    session, answer = prepared()
    first = publish(session, answer)
    assert publish(session, answer) == first
    assert len(session.snapshot()["played"]) == 1
    with pytest.raises(RuntimeError):
        publish(session, answer, operation_id="another-operation")


def test_cancelled_closed_or_unapproved_pending_answer_cannot_publish():
    session, answer = prepared()
    old_epoch = session.epoch
    session.cancel()
    with pytest.raises(RuntimeError):
        session.publish_text("q", old_epoch, answer, instance_id="i", operation_id="o", request_epoch=0)
    assert session.snapshot()["played"] == []
    session, answer = prepared()
    session._received["q"]["response"]["final_check"]["status"] = "reject"
    with pytest.raises(RuntimeError):
        publish(session, answer)
    assert session.snapshot()["played"] == []
    session, answer = prepared()
    session.finish()
    with pytest.raises(RuntimeError):
        publish(session, answer)


def test_no_browser_connection_still_publishes_and_can_be_recovered():
    with running() as (client, engine, manager):
        sid = begin(client)
        submit(client, sid)
        # No EventSource or render/read acknowledgement was ever created.
        state = settled(client, sid)
        assert state["turns"][0]["delivery_receipt"] is not None
        later = client.get(f"/ui/v1/sessions/{sid}/turns/question").json()
        assert later == state["turns"][0] and engine.calls == 1


def test_cancel_discards_a_backend_that_returns_a_valid_late_answer():
    engine = TextEngine("demo")
    original = engine.answer
    entered = threading.Event()
    release = threading.Event()

    def noncooperative(session, rid, text, emit, cancelled, epoch):
        answer = original(session, rid, text, emit, threading.Event(), epoch)
        entered.set()
        assert release.wait(4)
        return answer

    engine.answer = noncooperative
    app = create_app(backend="demo", engine_factory=lambda:engine)
    with TestClient(app) as client:
        assert app.state.coordinator.initialized.wait(3)
        try:
            sid = begin(client)
            submit(client, sid)
            assert entered.wait(2)
            assert client.get(f"/ui/v1/sessions/{sid}/turns/question").json()["delivery_receipt"] is None
            client.post(f"/ui/v1/sessions/{sid}/cancel",
                        json={"request_id":"cancel", "target_request_id":"question"})
        finally:
            release.set()
        state = settled(client, sid)
        assert state["turns"][0]["status"] == "CANCELLED"
        assert state["turns"][0]["answer"] is None and state["turns"][0]["delivery_receipt"] is None
        business = app.state.coordinator.conversations[sid].business
        assert business.snapshot()["played"] == []
        events, _, _ = app.state.coordinator.event_batch(sid, 0)
        assert "answer.ready" not in [event["event"] for event in events]
        # Late rejected answers do not supply follow-up context.
        submit(client, sid, "followup", "那这个呢？")
        followup = settled(client, sid)["turns"][-1]
        assert followup["answer_source"] == "TEMPLATE"


def test_cancelling_after_publication_does_not_retract_committed_history():
    with running() as (client, engine, manager):
        sid = begin(client)
        submit(client, sid)
        before = settled(client, sid)
        response = client.post(f"/ui/v1/sessions/{sid}/cancel",
                               json={"request_id":"late-cancel", "target_request_id":"question"})
        assert response.status_code == 409
        assert client.get(f"/ui/v1/sessions/{sid}").json()["turns"] == before["turns"]
        assert len(manager.conversations[sid].business.snapshot()["played"]) == 1


def test_sse_answer_carries_same_receipt_as_query_and_snapshot():
    with server() as (client, sid, manager):
        state = complete(client, sid)
        with client.stream("GET", "/ui/v1/events", params={"session_id":sid,"after":0}) as response:
            events = events_until(response, "turn.completed")
        answer = next(event for event in events if event["event"] == "answer.ready")
        queried = client.get(f"/ui/v1/sessions/{sid}/turns/question").json()
        assert answer["data"]["delivery_receipt"] == queried["delivery_receipt"] == state["turns"][0]["delivery_receipt"]
        assert answer["epoch"] == queried["delivery_receipt"]["epoch"]


def test_server_restart_does_not_reuse_old_receipts_or_session_identity():
    with running() as (client, engine, manager):
        sid = begin(client)
        submit(client, sid)
        receipt = settled(client, sid)["turns"][0]["delivery_receipt"]
    with running() as (client, engine, manager):
        assert manager.journal.instance_id != receipt["instance_id"]
        assert client.get(f"/ui/v1/sessions/{sid}/turns/question").status_code == 404


@pytest.mark.parametrize("result", [
    {"text":"每次疼痛持续10分钟。", "status":"OK", "eos":"false"},
    {"text":"每次疼痛持续10分钟。", "status":"OK", "eos":True, "id":"foreign:request"},
    {"text":"每次疼痛持续10分钟。", "status":"OK", "eos":True, "actual_backend":"FPGA"},
    {"text":42, "status":"OK", "eos":True},
])
def test_malformed_model_result_is_an_error_without_receipt(result):
    with running() as (client, engine, manager):
        engine.model.generate = lambda *args,**kwargs:deepcopy(result)
        sid = begin(client)
        submit(client, sid)
        state = settled(client, sid)
        assert state["turns"][0]["status"] == "FAILED"
        assert state["turns"][0]["error"]["code"] == "MODEL_ERROR"
        assert state["turns"][0]["delivery_receipt"] is None
        assert manager.conversations[sid].business.snapshot()["played"] == []


def test_incomplete_generation_publishes_only_checked_template_with_demo_counts():
    with running() as (client, engine, manager):
        engine.model.generate = lambda *args,**kwargs:{"text":"每次疼痛持续99分钟。", "status":"OK", "eos":False}
        sid = begin(client)
        submit(client, sid)
        result = settled(client, sid)["turns"][0]
        assert result["answer"] == "每次疼痛持续10分钟。"
        assert result["answer_source"] == "TEMPLATE"
        assert result["delivery_receipt"]["model_called"] is False
        TurnResult.model_validate(result)


@pytest.mark.parametrize("status", ["CANCELLED", "ERROR"])
def test_backend_terminal_status_never_becomes_a_patient_answer(status):
    with running() as (client, engine, manager):
        engine.model.generate = lambda *args,**kwargs:{"text":"每次疼痛持续10分钟。", "status":status, "eos":False}
        sid = begin(client)
        submit(client, sid)
        result = settled(client, sid)["turns"][0]
        assert result["status"] == ("CANCELLED" if status == "CANCELLED" else "FAILED")
        assert result["delivery_receipt"] is None and result["answer"] is None


def test_native_timeout_has_truthful_checked_fallback_and_quarantines_backend():
    # Protocol fixture only; no real native process or model is run in this test.
    class Process:
        def poll(self):
            return None

    class TimeoutModel:
        broken = False
        p = Process()
        def generate(self, *args, **kwargs):
            return {"text":"", "status":"TIMEOUT", "eos":False}
        def close(self):
            pass

    engine = TextEngine("demo")
    engine.backend = "native"
    engine.model = TimeoutModel()
    app = create_app(backend="native", engine_factory=lambda:engine)
    with TestClient(app) as client:
        assert app.state.coordinator.initialized.wait(3)
        sid = begin(client)
        submit(client, sid)
        result = settled(client, sid)["turns"][0]
        assert result["answer_source"] == "TIMEOUT"
        assert result["answer"] == "每次疼痛持续10分钟。"
        assert result["delivery_receipt"]["model_called"] is True
        assert result["actual_backend"] == "CPU_REFERENCE"
        assert client.get("/ui/v1/status").json()["ready"] is False
        assert submit(client, sid, request_id="next").status_code == 503
        TurnResult.model_validate(result)


def test_handoff_contract_files_match_runtime_models():
    root = Path(__file__).resolve().parents[2] / "docs" / "contracts"
    assert json.loads((root / "text-delivery.schema.json").read_text("utf-8")) == DeliveryReceipt.model_json_schema()
    assert json.loads((root / "turn-result.schema.json").read_text("utf-8")) == TurnResult.model_json_schema()


def test_browser_cannot_supply_publication_approval_or_receipt():
    with running() as (client, engine, manager):
        sid = begin(client)
        response = client.post(f"/ui/v1/sessions/{sid}/turns", json={
            "request_id":"spoof", "text":"哪里疼？", "validation_status":"pass",
            "delivery_receipt":{"delivery_kind":"WEB_TEXT_PUBLISHED"},
        })
        assert response.status_code == 400 and engine.calls == 0
        assert client.get(f"/ui/v1/sessions/{sid}").json()["turns"] == []

