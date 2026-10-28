"""Bounded real-HTTP handoff probe; run against a fresh, explicitly selected local service."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import ProxyHandler, Request, build_opener
import uuid

from .delivery import TurnResult
from .evaluation import EvaluationResult


class ProbeFailure(RuntimeError):
    pass


def run_probe(base_url: str, expected_backend: str, timeout_s: float = 60, *, include_evaluation=False,
              single_demo=False):
    parsed = urlsplit(base_url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise ValueError("Use an explicit local HTTP service origin")
    if expected_backend not in ("demo", "native", "managed-pl") or not 0 < timeout_s <= 600:
        raise ValueError("Invalid backend or timeout")
    base = base_url.rstrip("/")
    opener = build_opener(ProxyHandler({}))
    request_prefix = "accept-" + uuid.uuid4().hex
    report = {"schema_version":"delivery-acceptance.v1", "started_at":datetime.now(timezone.utc).isoformat(),
              "expected_backend":expected_backend, "base_url":base, "verdict":"FAILED",
              "checks":[], "scope":"HTTP text delivery only; not medical, PL or board acceptance"}
    report["single_demo"] = single_demo
    include_evaluation = include_evaluation or single_demo
    sid = None
    rid = request_prefix + "-q"

    def call(path, body=None):
        raw = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(base + path, data=raw, headers={"Content-Type":"application/json"})
        try:
            response = opener.open(request, timeout=min(timeout_s, 10))
        except HTTPError as error:
            response = error
        with response:
            return response.code, json.loads(response.read().decode("utf-8"))

    def require(condition, name):
        if not condition:
            raise ProbeFailure(name)
        report["checks"].append(name)

    try:
        deadline = time.monotonic() + timeout_s
        while True:
            code, status = call("/ui/v1/status")
            if status.get("ready") or status.get("phase") == "FAILED" or time.monotonic() >= deadline:
                break
            time.sleep(.1)
        require(code == 200 and status["backend"]["configured"] == expected_backend,
                "explicit_backend_matches")
        report["service_status"] = status
        require(status["ready"] and not status["busy"], "service_ready_and_idle")
        active = status.get("current_session_id")
        if active:
            _, old = call("/ui/v1/sessions/" + quote(active, safe=""))
            require(old.get("closed") is True, "no_existing_open_consultation")
        code, created = call("/ui/v1/sessions", {"request_id":request_prefix,"case_id":"SYN_CP_01"})
        require(code == 201, "session_created")
        sid = created["session_id"]
        path = f"/ui/v1/sessions/{sid}"
        question = {"request_id":rid,"text":"每次疼痛持续多久？"}
        code, accepted = call(path + "/turns", question)
        require(code == 202, "turn_accepted")
        deadline = time.monotonic() + timeout_s
        while True:
            code, turn = call(path + "/turns/" + rid)
            if turn.get("status") != "RUNNING" or time.monotonic() >= deadline:
                break
            time.sleep(.05)
        require(code == 200 and turn.get("status") == "COMPLETED", "turn_completed")
        checked = TurnResult.model_validate(turn)
        receipt = checked.delivery_receipt
        require(receipt.session_id == sid and receipt.instance_id == status["instance_id"]
                and receipt.operation_id == accepted["operation_id"], "receipt_identity_and_hash_valid")
        report["turn_result"] = turn
        if not single_demo:
            code, replay = call(path + "/turns", question)
            require(code == 202 and replay.get("replayed") is True
                    and replay["operation_id"] == accepted["operation_id"], "retry_reuses_operation")
        _, snapshot = call(path)
        require(len(snapshot["turns"]) == 1 and snapshot["turns"][0] == turn,
                "snapshot_recovers_same_single_publication_without_browser_ack")
        if not single_demo:
            code, conflict = call(path + "/turns", dict(question, text="哪里疼？"))
            require(code == 409 and conflict["error"]["code"] == "REQUEST_CONFLICT", "changed_retry_rejected")
            code, late = call(path + "/cancel", {"request_id":request_prefix+"-c","target_request_id":rid})
            require(code == 409 and late["error"]["code"] == "NO_MATCHING_OPERATION",
                    "late_cancel_cannot_retract_publication")
        code, _ = call(path + "/finish", {"request_id":request_prefix+"-finish"})
        require(code == 200, "session_finished")
        _, frozen = call(path + "/turns/" + rid)
        require(frozen == turn, "receipt_stable_after_finish")
        if include_evaluation:
            report["scope"] = "HTTP text delivery and chief template evaluation; not medical, PL or board acceptance"
            code, evaluation = call(path + "/evaluation")
            parsed_evaluation = EvaluationResult.model_validate(evaluation)
            digest_payload = {key:value for key,value in evaluation.items() if key != "evaluation_id"}
            digest = hashlib.sha256(json.dumps(digest_payload, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode("utf-8")).hexdigest()
            require(code == 200 and parsed_evaluation.session_id == sid
                    and parsed_evaluation.instance_id == receipt.instance_id
                    and parsed_evaluation.case_sha256 == receipt.case_sha256
                    and digest == parsed_evaluation.evaluation_id,
                    "evaluation_identity_schema_and_digest_valid")
            duration = next(topic for topic in parsed_evaluation.topics if topic.topic_id == "duration")
            require(parsed_evaluation.covered_topics == ["duration"]
                    and parsed_evaluation.rule_score["score"] == duration.points == 10
                    and len(duration.evidence) == 1 and duration.evidence[0].request_id == rid
                    and duration.evidence[0].question == turn["question"]
                    and duration.evidence[0].answer_published,
                    "evaluation_matches_probe_question_evidence")
            if not single_demo:
                code, _ = call(path + "/finish", {"request_id":request_prefix+"-finish-retry"})
                _, repeated_evaluation = call(path + "/evaluation")
                require(code == 200 and repeated_evaluation == evaluation,
                        "evaluation_stable_after_repeated_finish_and_query")
            report["evaluation"] = evaluation
        if expected_backend == "demo":
            require(checked.answer_source == "DEMO_RULE" and not receipt.model_called,
                    "demo_does_not_claim_model_execution")
            report["verdict"] = "PASS_DEMO_TEXT_DELIVERY"
        elif checked.answer_source == "MODEL" and receipt.model_called:
            actual_kind = "FPGA_REAL" if expected_backend == "managed-pl" else "CPU_REFERENCE"
            require(receipt.actual_backend == actual_kind
                    and status["backend"]["execution_kind"] == actual_kind, "actual_backend_matches_selected_path")
            report["verdict"] = ("PASS_MANAGED_PL_TEXT_DELIVERY" if expected_backend == "managed-pl"
                                 else "PASS_NATIVE_TEXT_DELIVERY")
        else:
            report["verdict"] = ("PARTIAL_MANAGED_PL_USED_CHECKED_FALLBACK" if expected_backend == "managed-pl"
                                 else "PARTIAL_NATIVE_USED_CHECKED_FALLBACK")
        report["joint_board_signoff"] = "NOT_TESTED"
    except Exception as error:
        report["failure"] = {"type":type(error).__name__, "message":str(error)}
    finally:
        if sid:
            # Only this probe's session/request may be cancelled or closed during cleanup.
            try:
                _, snapshot = call(f"/ui/v1/sessions/{sid}")
                if snapshot.get("active_request_id") == rid:
                    if single_demo:
                        report["cleanup"] = {"status":"left_active_for_PS_owner", "session_id":sid,
                                             "note":"Single demo sends no cancellation or restart"}
                    else:
                        call(f"/ui/v1/sessions/{sid}/cancel", {
                            "request_id":request_prefix+"-cleanup", "target_request_id":rid})
                        report["cleanup"] = {"status":"cancel_pending", "session_id":sid,
                                             "note":"Wait for unwind; this probe does not close an active turn"}
                elif not snapshot.get("closed"):
                    call(f"/ui/v1/sessions/{sid}/finish", {"request_id":request_prefix+"-cleanup"})
            except Exception:
                report["cleanup"] = "Probe session may remain; inspect before another acceptance run"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main():
    parser = argparse.ArgumentParser(description="第四任务：纯文字交付 HTTP 验收（会创建一场合成问诊）")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-backend", choices=("demo", "native", "managed-pl"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--include-evaluation", action="store_true", help="Also verify task-5 frozen chief feedback")
    parser.add_argument("--single-demo", action="store_true", help="One question and chief feedback only; no cancel/retry/fault probes")
    args = parser.parse_args()
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error("output must be a new file in an existing directory")
    try:
        report = run_probe(args.base_url, args.expected_backend, args.timeout,
                           include_evaluation=args.include_evaluation, single_demo=args.single_demo)
    except ValueError as error:
        parser.error(str(error))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"verdict":report["verdict"], "output":str(args.output)}, ensure_ascii=False))
    return 0 if report["verdict"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())

