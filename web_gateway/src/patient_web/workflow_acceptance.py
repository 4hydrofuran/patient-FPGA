"""Task 6: repeatable no-model HTTP/SSE workflow, with isolated service by default."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
import uuid

import uvicorn

from .acceptance import ProbeFailure
from .api import create_app
from .delivery import TurnResult
from .evaluation import EvaluationResult


@contextmanager
def isolated_service(port=0):
    """Own only this fresh loopback service; never restart an external service."""
    sock = socket.socket()
    if os.name == "posix":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    app = create_app(backend="demo", demo_lab=True)
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", timeout_graceful_shutdown=2))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        if not server.started or not app.state.coordinator.initialized.wait(3):
            raise RuntimeError("Isolated service failed to start")
        yield origin
    finally:
        server.should_exit = True
        thread.join(15)
        sock.close()
        if thread.is_alive():
            raise RuntimeError("Isolated service did not stop")


class WorkflowProbe:
    def __init__(self, base_url):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/")):
            raise ValueError("Use an explicit loopback HTTP origin")
        self.base = base_url.rstrip("/")
        self.opener = build_opener(ProxyHandler({}))
        self.prefix = "flow-" + uuid.uuid4().hex
        self.owned = []
        self.report = {"schema_version": "workflow-acceptance.v1", "verdict": "FAILED",
                       "started_at": datetime.now(timezone.utc).isoformat(), "base_url": self.base,
                       "scope": "No-model software workflow over real HTTP/SSE",
                       "checks": [], "sessions": [], "events": [],
                       "not_verified": ["real_model", "KV260", "physical_touch", "soft_keyboard", "audio", "PL"],
                       "restart": "NOT_TESTED_EXTERNAL_SERVICE"}

    def call(self, path, body=None):
        raw = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(self.base + path, data=raw, headers={"Content-Type": "application/json"})
        try:
            response = self.opener.open(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.code, json.loads(response.read().decode("utf-8"))

    def check(self, condition, name):
        if not condition:
            raise ProbeFailure(name)
        self.report["checks"].append(name)

    def wait(self, path, predicate, name, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            code, data = self.call(path)
            if code == 200 and predicate(data):
                return data
            time.sleep(.02)
        raise ProbeFailure(name)

    def begin(self, tag, case="SYN_CP_01"):
        code, result = self.call("/ui/v1/sessions", {"request_id": self.prefix + tag, "case_id": case})
        self.check(code == 201, tag + ":session_created")
        path = "/ui/v1/sessions/" + result["session_id"]
        self.owned.append(path)
        return path

    def arm(self, scenario, delay=.2):
        code, _ = self.call("/ui/v1/demo-lab", {"scenario": scenario, "delay_s": delay})
        self.check(code == 200, scenario + ":armed")

    def submit(self, path, tag, text="每次疼痛持续多久？"):
        body = {"request_id": self.prefix + tag, "text": text}
        code, result = self.call(path + "/turns", body)
        self.check(code == 202, tag + ":accepted")
        return body, result

    def settled(self, path):
        return self.wait(path, lambda s: not s["active_request_id"], "turn_unwind_deadline")

    def checked(self, turn, expected, source, name):
        validated = TurnResult.model_validate(turn)
        receipt = validated.delivery_receipt
        self.check(validated.status == "COMPLETED" and validated.answer == expected
                   and validated.answer_source == source and receipt is not None
                   and not receipt.model_called and receipt.actual_backend is None,
                   name + ":checked_text_and_honest_source")

    def events(self, path):
        snapshot = self.call(path)[1]
        terminal = "evaluation.ready" if snapshot["closed"] else {
            "COMPLETED": "turn.completed", "FAILED": "turn.failed", "CANCELLED": "turn.cancelled"
        }[snapshot["turns"][-1]["status"]]
        items = []
        deadline = time.monotonic() + 5
        with self.opener.open(self.base + "/ui/v1/events?session_id=" + snapshot["session_id"] + "&after=0",
                              timeout=5) as response:
            while time.monotonic() < deadline:
                line = response.readline().decode("utf-8")
                if not line:
                    break
                if line.startswith("data: "):
                    item = json.loads(line[6:])
                    items.append(item)
                    if item["event"] == terminal and item["seq"] == snapshot["cursor"]:
                        break
        self.check(bool(items) and items[-1]["event"] == terminal, "SSE:terminal_replayed")
        sequences = [item["seq"] for item in items]
        self.check(sequences == sorted(set(sequences)) and "generation.started" not in
                   [item["event"] for item in items], "SSE:ordered_without_fake_model_events")
        self.report["events"].extend(items)
        return items

    def freeze(self, path):
        code, _ = self.call(path + "/finish", {"request_id": self.prefix + "-finish-" + str(len(self.owned))})
        self.check(code == 200, "finish:accepted")
        result = self.call(path + "/evaluation")[1]
        EvaluationResult.model_validate(result)
        self.call(path + "/finish", {"request_id": self.prefix + "-repeat-" + str(len(self.owned))})
        self.check(self.call(path + "/evaluation")[1] == result, "evaluation:frozen_across_retry_and_query")
        self.report["sessions"].append({"snapshot": self.call(path)[1], "evaluation": result})
        return result

    def execute(self):
        try:
            status = self.wait("/ui/v1/status", lambda s: s["ready"], "service_ready")
            self.report["instance_id"] = status["instance_id"]
            self.check(status["backend"]["configured"] == "demo" and status.get("demo_lab") is True,
                       "explicit_demo_lab_required")
            self.check(status["current_session_id"] is None and not status["busy"],
                       "fresh_service_required_preserve_existing_sessions")
            # A normal visit plus a question requiring review.
            visit = self.begin("-visit")
            for tag, question, expected, source in [
                ("-location", "哪里疼？", "疼痛在胸骨后。", "DEMO_RULE"),
                ("-duration", "每次疼痛持续多久？", "每次疼痛持续10分钟。", "DEMO_RULE"),
            ]:
                self.submit(visit, tag, question)
                self.checked(self.settled(visit)["turns"][-1], expected, source, tag)
            self.submit(visit, "-review", "不是没有呼吸困难吗？")
            snapshot = self.settled(visit)
            self.check(self.call(visit)[1]["turns"] == snapshot["turns"], "refresh:same_process_history_restored")
            evaluation = self.freeze(visit)
            self.check(evaluation["rule_score"]["score"] == 20
                       and set(evaluation["covered_topics"]) == {"location", "duration"}
                       and len(evaluation["review_items"]) == 1
                       and evaluation["summary_source"] == "RULE_TEMPLATE", "visit:20_points_review_and_chief_template")
            self.check(all(e["request_id"] == self.prefix + "-" + topic["topic_id"]
                           for topic in evaluation["topics"] if topic["covered"] for e in topic["evidence"]),
                       "visit:score_evidence_matches_questions")
            events = self.events(visit)
            for turn in snapshot["turns"]:
                names = [e["event"] for e in events if e["request_id"] == turn["request_id"]]
                self.check(names.index("answer.ready") < names.index("turn.completed"), "visit:publish_before_complete")
                if "validation.started" in names:
                    self.check(names.index("validation.started") < names.index("answer.ready"), "visit:check_before_publish")
            self.check(self.call(visit + "/turns", {"request_id": self.prefix + "-closed", "text": "哪里疼？"})[0] == 409,
                       "closed_visit:reject_more_questions")
            # All faults use the real coordinator, checker and publication gate.
            faults = self.begin("-faults")
            self.arm("delayed", 1.5)
            question, accepted = self.submit(faults, "-slow")
            active = self.wait("/ui/v1/demo-lab", lambda s: bool(s["active"] and s["active"]["adapter_invoked"]), "delay_entered")
            self.check(active["active"]["scenario"] == "delayed", "delay:adapter_entered")
            self.check(self.call(faults)[1]["turns"][0]["answer"] is None, "delay:no_early_answer_on_refresh")
            code, replay = self.call(faults + "/turns", question)
            self.check(code == 202 and replay["replayed"] and replay["operation_id"] == accepted["operation_id"],
                       "retry:one_operation_while_busy")
            self.check(self.call(faults + "/turns", dict(question, text="哪里疼？"))[0] == 409, "retry:changed_payload_rejected")
            self.check(self.call(faults + "/turns", dict(question, request_id=self.prefix + "-busy"))[0] == 409,
                       "busy:no_hidden_queue")
            self.check(self.call("/ui/v1/demo-lab", {"scenario": "failure"})[0] == 409, "busy:scenario_cannot_change_active_turn")
            self.checked(self.settled(faults)["turns"][-1], "每次疼痛持续10分钟。", "DEMO_RULE", "delay")
            self.check(len(self.call(faults)[1]["turns"]) == 1, "retry:single_history_entry")

            self.arm("delayed", 1.5)
            cancelled, _ = self.submit(faults, "-cancel", "哪里疼？")
            self.wait("/ui/v1/demo-lab", lambda s: bool(s["active"] and s["active"]["adapter_invoked"]), "cancel_adapter_entered")
            code, _ = self.call(faults + "/cancel", {"request_id": self.prefix + "-cancel-command", "target_request_id": cancelled["request_id"]})
            self.check(code == 202 and self.call(faults)[1]["phase"] == "CANCELLING", "cancel:pending_until_unwind")
            self.check(self.call(faults + "/finish", {"request_id": self.prefix + "-busy-finish"})[0] == 409,
                       "cancel:finish_rejected_until_unwind")
            turn = self.settled(faults)["turns"][-1]
            self.check(turn["status"] == "CANCELLED" and turn["answer"] is None and turn["delivery_receipt"] is None,
                       "cancel:late_answer_not_published")
            for scenario, source in [("wrong_fact", "TEMPLATE"), ("timeout", "TEMPLATE")]:
                self.arm(scenario)
                self.submit(faults, "-" + scenario)
                self.checked(self.settled(faults)["turns"][-1], "每次疼痛持续10分钟。", source, scenario)
            self.arm("failure")
            self.submit(faults, "-failure")
            turn = self.settled(faults)["turns"][-1]
            self.check(turn["status"] == "FAILED" and turn["answer"] is None and turn["delivery_receipt"] is None,
                       "failure:no_answer_or_receipt")
            self.submit(faults, "-recovered")
            self.checked(self.settled(faults)["turns"][-1], "每次疼痛持续10分钟。", "DEMO_RULE", "recovery")
            self.check(self.call("/ui/v1/status")[1]["ready"], "recovery:service_ready")
            fault_eval = self.freeze(faults)
            self.check(fault_eval["rule_score"]["score"] == 20, "scoring:accepted_questions_retained_after_cancel_or_failure")
            events = self.events(faults)
            bad_ids = {self.prefix + "-cancel", self.prefix + "-failure"}
            self.check(not any(e["event"] == "answer.ready" and e["request_id"] in bad_ids for e in events),
                       "SSE:no_cancelled_or_failed_answer")
            self.check("99分钟" not in json.dumps(events, ensure_ascii=False), "SSE:rejected_candidate_never_exposed")
            self.report["simulation_history"] = self.call("/ui/v1/demo-lab")[1]["history"]
            self.check(all(any(row["request_id"] == self.prefix + "-" + scenario and row["injection"] == scenario
                                   and row["adapter_invoked"] for row in self.report["simulation_history"])
                               for scenario in ("wrong_fact", "timeout", "failure")), "faults:injections_actually_executed")
            empty = self.begin("-empty", "SYN_CP_02")
            self.check(self.call(empty)[1]["turns"] == [], "new_case:history_isolated")
            empty_eval = self.freeze(empty)
            self.check(empty_eval["rule_score"]["score"] == 0 and len(empty_eval["missing_topics"]) == 10
                       and empty_eval["frozen_turn_count"] == 0, "empty_visit:zero_score_complete_feedback")
            self.check(self.call(visit + "/evaluation")[1] == evaluation, "new_case:previous_evaluation_unchanged")
            self.report["verdict"] = "PASS_DEMO_WORKFLOW"
        except Exception as error:
            self.report["failure"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            for path in self.owned:
                try:
                    state = self.call(path)[1]
                    if state.get("active_request_id"):
                        self.call(path + "/cancel", {"request_id": self.prefix + "-cleanup", "target_request_id": state["active_request_id"]})
                        self.settled(path)
                    if not state.get("closed"):
                        self.call(path + "/finish", {"request_id": self.prefix + "-cleanup-finish"})
                except Exception:
                    self.report.setdefault("cleanup_errors", []).append(path)
            if self.report.get("cleanup_errors"):
                self.report["verdict"] = "FAILED"
            self.report["finished_at"] = datetime.now(timezone.utc).isoformat()
        return self.report


def run_isolated():
    with isolated_service() as origin:
        report = WorkflowProbe(origin).execute()
    if report["verdict"] == "PASS_DEMO_WORKFLOW":
        # A second owned instance at the same address must reject old session IDs.
        port = urlsplit(origin).port
        try:
            with isolated_service(port) as restarted:
                probe = WorkflowProbe(restarted)
                status = probe.wait("/ui/v1/status", lambda s: s["ready"], "restart_ready")
                old = report["sessions"][0]["snapshot"]["session_id"]
                if (status["instance_id"] == report["instance_id"] or status["current_session_id"] is not None
                        or probe.call("/ui/v1/sessions/" + old)[0] != 404):
                    raise ProbeFailure("restart_did_not_clear_memory_sessions")
                report["restart"] = {"verdict": "PASS", "new_instance_id": status["instance_id"], "old_session_http_status": 404}
                report["checks"].append("restart:new_instance_empty_memory_and_old_session_rejected")
        except Exception as error:
            report["verdict"] = "FAILED"
            report["failure"] = {"type": type(error).__name__, "message": str(error)}
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main():
    parser = argparse.ArgumentParser(description="任务6：无模型完整流程验收，默认自动启动及关闭独立本机服务")
    parser.add_argument("--base-url", help="Optional fresh --backend demo --demo-lab service; external service is never restarted")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error("output must be a new file in an existing directory")
    try:
        report = WorkflowProbe(args.base_url).execute() if args.base_url else run_isolated()
    except ValueError as error:
        parser.error(str(error))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"verdict": report["verdict"], "checks": len(report["checks"]), "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["verdict"] == "PASS_DEMO_WORKFLOW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
