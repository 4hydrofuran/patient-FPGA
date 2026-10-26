"""Frozen chief feedback preserves the A02 rubric and names its exact question evidence."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading

import pytest

from patient_web.engine import TextEngine
from patient_web.errors import OperationCancelled
from patient_web.evaluation import EvaluationResult, TOPICS
from patient_web.reference.scoring import score
from test_commands import begin, running, settled, submit
from test_events import events_until, server


def finish(client, sid, request_id="finish"):
    result = client.post(f"/ui/v1/sessions/{sid}/finish", json={"request_id": request_id})
    assert result.status_code == 200, result.text
    response = client.get(f"/ui/v1/sessions/{sid}/evaluation")
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_consultation_has_zero_score_and_no_invented_evidence():
    with running() as (client, engine, manager):
        sid = begin(client)
        result = finish(client, sid)
        EvaluationResult.model_validate(result)
        assert result["rule_score"]["score"] == 0
        assert result["covered_topics"] == [] and len(result["missing_topics"]) == 10
        assert result["frozen_turn_count"] == result["scoring_event_count"] == 0
        assert all(item["evidence"] == [] for item in result["topics"])
        assert "尚无可计分" in result["summary_text"]
        assert result["review_items"] == [] and result["summary_source"] == "RULE_TEMPLATE"
        assert result["rule_score"]["clinical_validity"] is None
        assert result["review_status"] == "PENDING_TEACHER_REVIEW"
        assert "临床能力" in result["disclaimer"]


def test_repeat_questions_cover_each_topic_once_with_all_question_evidence():
    with running() as (client, engine, manager):
        sid = begin(client)
        for request_id, question in (("q1", "哪里疼？"), ("q2", "持续多久？"), ("q3", "哪里疼？")):
            assert submit(client, sid, request_id, question).status_code == 202
            settled(client, sid)
        before = manager.conversations[sid].business.snapshot()
        expected_score = score(deepcopy(before["received"]))
        result = finish(client, sid)
        assert result["rule_score"] == expected_score
        assert result["rule_score"]["score"] == 20
        assert result["covered_topics"] == ["location", "duration"]
        location = next(item for item in result["topics"] if item["topic_id"] == "location")
        assert [item["request_id"] for item in location["evidence"]] == ["q1", "q3"]
        assert [item["question_number"] for item in location["evidence"]] == [1, 3]
        assert "已覆盖：疼痛位置、持续时间。" in result["summary_text"]
        assert "缓解因素" in result["recommendations"][0]
        assert "胸骨后" not in json.dumps(result, ensure_ascii=False)


def test_all_topics_have_exactly_full_coverage_without_ability_grade():
    questions = ["哪里疼？", "怎么个疼？", "什么时候开始的？", "持续多久？", "严重吗？",
                 "牵扯其他地方吗？", "什么情况下加重？", "什么情况缓解？", "呼吸困难吗？", "过敏吗？"]
    with running() as (client, engine, manager):
        sid = begin(client)
        for index, question in enumerate(questions):
            submit(client, sid, f"q{index}", question)
            settled(client, sid)
        result = finish(client, sid)
        assert result["rule_score"]["score"] == 100
        assert set(result["covered_topics"]) == set(TOPICS)
        assert result["missing_topics"] == []
        assert "已全部覆盖" in result["summary_text"]
        assert all(item["points"] == 10 and item["evidence"] for item in result["topics"])
        assert "合格" not in result["summary_text"] and "优秀" not in result["summary_text"]


def test_review_question_is_separate_from_confirmed_score_and_retains_original_text():
    with running() as (client, engine, manager):
        sid = begin(client)
        question = "不是没有呼吸困难吗？"
        submit(client, sid, "ambiguous", question)
        settled(client, sid)
        result = finish(client, sid)
        assert result["rule_score"]["score"] == 0 and result["covered_topics"] == []
        item = result["review_items"][0]
        assert item["question"] == question and item["question_number"] == 1
        assert item["reason"] == "double_negation_ambiguous"
        assert "双重否定" in item["reason_label"]
        assert "1 条提问待复核" in result["summary_text"]
        assert all(not topic["evidence"] for topic in result["topics"])


def test_cancelled_valid_late_answer_still_has_question_score_without_claiming_publication():
    engine = TextEngine("demo")
    original = engine.answer
    gate, entered = threading.Event(), threading.Event()
    def delayed(*args, **kwargs):
        answer = original(*args, **kwargs)
        entered.set()
        assert gate.wait(3)
        return answer
    engine.answer = delayed
    with running(factory=lambda:engine) as (client, unused, manager):
        try:
            sid = begin(client)
            submit(client, sid)
            assert entered.wait(2)
            client.post(f"/ui/v1/sessions/{sid}/cancel", json={"request_id":"cancel", "target_request_id":"question"})
        finally:
            gate.set()
        settled(client, sid)
        result = finish(client, sid)
        assert result["rule_score"]["score"] == 10
        topic = next(item for item in result["topics"] if item["topic_id"] == "duration")
        assert topic["evidence"][0]["turn_status"] == "CANCELLED"
        assert topic["evidence"][0]["answer_published"] is False
        assert "不会自动撤销" in result["scoring_note"]


def test_evidence_uses_request_identity_when_public_and_business_turn_numbers_differ():
    engine = TextEngine("demo")
    original = engine.answer
    gate, entered = threading.Event(), threading.Event()
    def delayed(session, request_id, *args):
        if request_id == "before-business":
            entered.set()
            assert gate.wait(3)
            raise OperationCancelled()
        return original(session, request_id, *args)
    engine.answer = delayed
    with running(factory=lambda:engine) as (client, unused, manager):
        try:
            sid = begin(client)
            submit(client, sid, "before-business")
            assert entered.wait(2)
            client.post(f"/ui/v1/sessions/{sid}/cancel", json={"request_id":"cancel", "target_request_id":"before-business"})
        finally:
            gate.set()
        settled(client, sid)
        submit(client, sid, "second", "哪里疼？")
        settled(client, sid)
        result = finish(client, sid)
        item = result["topics"][0]["evidence"][0]
        assert result["frozen_turn_count"] == 2 and result["scoring_event_count"] == 1
        assert item["turn_id"] == 1 and item["question_number"] == 2
        assert item["request_id"] == "second" and item["question"] == "哪里疼？"


def test_evaluation_is_frozen_idempotent_and_isolated_from_new_session():
    with running() as (client, engine, manager):
        sid = begin(client)
        submit(client, sid)
        settled(client, sid)
        result = finish(client, sid)
        assert finish(client, sid, "retry") == result
        assert finish(client, sid) == result
        detached = manager.evaluation(sid)
        detached["topics"][0]["points"] = 999
        assert manager.evaluation(sid) == result
        new_sid = begin(client, "second-session", "SYN_CP_02")
        empty = finish(client, new_sid)
        assert empty["rule_score"]["score"] == 0
        assert empty["evaluation_id"] != result["evaluation_id"]
        assert client.get(f"/ui/v1/sessions/{sid}/evaluation").json() == result


def test_finish_waits_for_active_turn_and_emits_ready_only_after_frozen_result():
    with running(blocking=True) as (client, engine, manager):
        sid = begin(client)
        submit(client, sid)
        assert engine.entered.wait(2)
        assert client.get(f"/ui/v1/sessions/{sid}/evaluation").status_code == 409
        assert client.post(f"/ui/v1/sessions/{sid}/finish", json={"request_id":"f"}).status_code == 409
        assert manager.conversations[sid].evaluation is None
        engine.release.set()
        settled(client, sid)
        result = finish(client, sid)
        finish(client, sid, "again")
        events, _, _ = manager.event_batch(sid, 0)
        ready = [event for event in events if event["event"] == "evaluation.ready"]
        assert len(ready) == 1 and ready[0]["data"]["evaluation_id"] == result["evaluation_id"]
        assert manager.snapshot(sid)["evaluation_ready"] is True


def test_failed_formatting_does_not_half_close_session(monkeypatch):
    import patient_web.manager as module
    original = module.build_evaluation
    def fail(**kwargs):
        raise RuntimeError("format failure")
    with running() as (client, engine, manager):
        sid = begin(client)
        monkeypatch.setattr(module, "build_evaluation", fail)
        with pytest.raises(RuntimeError, match="format failure"):
            client.post(f"/ui/v1/sessions/{sid}/finish", json={"request_id":"f"})
        assert manager.snapshot(sid)["closed"] is False
        assert manager.conversations[sid].business.snapshot()["closed"] is False
        monkeypatch.setattr(module, "build_evaluation", original)
        assert finish(client, sid)["summary_status"] == "READY"


def test_real_sse_reconnect_contains_single_evaluation_identity():
    with server() as (client, sid, manager):
        result = finish(client, sid)
        with client.stream("GET", "/ui/v1/events", params={"session_id":sid, "after":0}) as response:
            events = events_until(response, "evaluation.ready")
        assert events[-2]["event"] == "session.finished"
        assert events[-1]["data"]["evaluation_id"] == result["evaluation_id"]


def test_display_assets_packaged_and_no_arbitrary_paths_exposed():
    root = Path(__file__).resolve().parents[2]
    static = root / "src/patient_web/static"
    with running() as (client, engine, manager):
        for name in ("clinic-background.png", "chief-physician.png", "chief-physician-speaking.png"):
            response = client.get(f"/display/{name}")
            assert response.status_code == 200 and response.headers["content-type"] == "image/png"
            assert hashlib.sha256(response.content).digest() == hashlib.sha256((static / name).read_bytes()).digest()
        assert client.get("/display/UPSTREAM.json").status_code == 404
        assert client.get("/display/evaluation.css").status_code == 200
        assert client.get("/display/tokens.css").status_code == 200
        assert client.get("/ui/v1/status").json()["capabilities"]["chief_summary_kind"] == "RULE_TEMPLATE"


def test_evaluation_schema_artifact_matches_runtime():
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "docs/contracts/chief-evaluation.schema.json").read_text(encoding="utf-8"))
    assert schema == EvaluationResult.model_json_schema()
