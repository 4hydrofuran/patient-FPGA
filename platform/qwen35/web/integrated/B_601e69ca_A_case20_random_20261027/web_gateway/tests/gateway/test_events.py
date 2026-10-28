"""Real HTTP streaming tests, including replay and bounded-buffer recovery."""

from contextlib import contextmanager
import json
import socket
import threading
import time

import httpx
import uvicorn

from patient_web.api import create_app
from patient_web.events import EventJournal


@contextmanager
def server(capacity=256):
    app = create_app(backend="demo", journal_capacity=capacity)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=2)
    instance = uvicorn.Server(config)
    thread = threading.Thread(target=lambda: instance.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 4
    while not instance.started and time.monotonic() < deadline:
        time.sleep(.01)
    assert instance.started
    assert app.state.coordinator.initialized.wait(3)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3) as client:
            response = client.post("/ui/v1/sessions", json={"request_id":"start", "case_id":"SYN_CP_01"})
            yield client, response.json()["session_id"], app.state.coordinator
    finally:
        instance.should_exit = True
        thread.join(5)
        sock.close()
        assert not thread.is_alive()


def events_until(response, name):
    result = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            item = json.loads(line[6:])
            result.append(item)
            if item["event"] == name:
                return result
    raise AssertionError("SSE ended before expected event")


def complete(client, sid, rid="question"):
    result = client.post(f"/ui/v1/sessions/{sid}/turns",
                         json={"request_id":rid, "text":"哪里疼？"})
    assert result.status_code == 202
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = client.get(f"/ui/v1/sessions/{sid}").json()
        if not snapshot["active_request_id"]:
            return snapshot
        time.sleep(.01)
    raise AssertionError("Turn failed to finish")


def test_real_sse_replays_ordered_checked_answer_and_completion():
    with server() as (client, sid, manager):
        complete(client, sid)
        with client.stream("GET", "/ui/v1/events", params={"session_id":sid, "after":0}) as response:
            assert response.headers["content-type"].startswith("text/event-stream")
            events = events_until(response, "turn.completed")
        names = [event["event"] for event in events]
        assert names.index("turn.accepted") < names.index("validation.started") < names.index("answer.ready") < names.index("turn.completed")
        assert "generation.started" not in names
        seqs = [event["seq"] for event in events]
        assert seqs == sorted(set(seqs))
        answer = next(event for event in events if event["event"] == "answer.ready")
        assert answer["data"]["text"] == "疼痛在胸骨后。"
        assert answer["data"]["answer_source"] == "DEMO_RULE"
        assert "answer_plan" not in str(events) and "candidate" not in str(events)


def test_initial_event_is_authoritative_snapshot():
    with server() as (client, sid, manager):
        snapshot = complete(client, sid)
        with client.stream("GET", "/ui/v1/events", params={"session_id":sid}) as response:
            event = events_until(response, "session.snapshot")[0]
        assert event["data"]["turns"] == snapshot["turns"]


def test_expired_buffer_resynchronizes_instead_of_silently_losing_events():
    with server(capacity=3) as (client, sid, manager):
        state = complete(client, sid)
        with client.stream("GET", "/ui/v1/events", params={"session_id":sid, "after":0}) as response:
            event = events_until(response, "session.snapshot")[0]
        assert event["data"]["resync_reason"] == "EVENT_BUFFER_EXPIRED"
        assert event["data"]["turns"] == state["turns"]


def test_last_event_id_resumes_without_replaying_earlier_events():
    with server() as (client, sid, manager):
        cursor = client.get(f"/ui/v1/sessions/{sid}").json()["cursor"]
        complete(client, sid)
        header = {"Last-Event-ID":f"{manager.journal.instance_id}:{cursor}"}
        with client.stream("GET", "/ui/v1/events", params={"session_id":sid}, headers=header) as response:
            events = events_until(response, "turn.completed")
        assert all(event["seq"] > cursor for event in events)
        assert events[0]["event"] == "turn.accepted"


def test_old_instance_resets_and_future_cursor_is_rejected():
    with server() as (client, sid, manager):
        with client.stream("GET", "/ui/v1/events", params={"session_id":sid},
                           headers={"Last-Event-ID":"old-instance:99999"}) as response:
            assert events_until(response, "session.snapshot")[0]["instance_id"] == manager.journal.instance_id
        assert client.get("/ui/v1/events", params={"session_id":sid,"after":99999}).status_code == 400
        assert client.get("/ui/v1/events", params={"session_id":sid},
                          headers={"Last-Event-ID":"bad-cursor"}).status_code == 400


def test_journal_is_bounded_and_filters_other_sessions():
    journal = EventJournal(3)
    for value in range(10):
        journal.emit("test", "other" if value % 2 else "mine", value=value)
    events, gap, cursor = journal.read(0, "mine")
    assert gap and len(journal.events) == 3 and cursor == 10
    assert all(event["session_id"] == "mine" for event in events)

