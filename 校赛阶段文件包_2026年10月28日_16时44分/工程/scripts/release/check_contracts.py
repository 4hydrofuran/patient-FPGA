"""A0 static contract checks; no runtime, medical or hardware validation."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ["quant_v1.md", "kernel_v1.yaml", "kernel_v1.hpp", "runtime_api_v1.yaml",
           "metrics_v1.json", "examples/handcheck_v1.json", "examples/b0_handcheck_v1.json", "examples/runtime_events_v1.json"]


def read_json(name):
    return json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))


def digest():
    h = hashlib.sha256()
    for name in sorted(CONTENT):
        h.update(name.encode("utf-8") + b"\0")
        h.update((ROOT / "contracts" / name).read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def resolve(api, ref):
    if not ref.startswith("#/"):
        raise ValueError("Only local schema references are supported")
    item = api
    for part in ref[2:].split("/"):
        item = item[part.replace("~1", "/").replace("~0", "~")]
    return item


def validate(value, schema, api):
    """Validate the JSON Schema subset used by our fixtures, not all OpenAPI."""
    if "$ref" in schema:
        return validate(value, resolve(api, schema["$ref"]), api)
    if "const" in schema:
        const = schema["const"]
        if value != const or (isinstance(const, bool) and type(value) is not bool):
            raise ValueError("const mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("enum mismatch")
    kinds = schema.get("type", [])
    if isinstance(kinds, str):
        kinds = [kinds]
    checks = {"null": value is None, "object": isinstance(value, dict),
              "array": isinstance(value, list), "string": isinstance(value, str),
              "integer": type(value) is int, "number": type(value) in (int, float),
              "boolean": type(value) is bool}
    if kinds and not any(checks[k] for k in kinds):
        raise ValueError("type mismatch")
    if isinstance(value, dict):
        if not set(schema.get("required", [])) <= value.keys():
            raise ValueError("missing required fields")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and not value.keys() <= properties.keys():
            raise ValueError("unexpected fields")
        for key in value.keys() & properties.keys():
            validate(value[key], properties[key], api)
    if isinstance(value, list):
        for item in value:
            validate(item, schema.get("items", {}), api)
    if isinstance(value, str):
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", float("inf")):
            raise ValueError("string length")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise ValueError("pattern mismatch")
    if type(value) in (int, float):
        if not schema.get("minimum", -float("inf")) <= value <= schema.get("maximum", float("inf")):
            raise ValueError("numeric range")


def check_stream(events, request, api):
    if not events or events[0]["event"] != "accepted":
        raise ValueError("accepted must be first")
    terminal = False
    for i, event in enumerate(events):
        validate(event, api["components"]["schemas"]["RuntimeEvent"], api)
        if terminal or event["seq"] != i:
            raise ValueError("out-of-order or post-terminal event")
        if i > 0 and event["event"] == "accepted":
            raise ValueError("duplicate accepted event")
        for key in ("request_id", "session_id"):
            if event[key] != request[key]:
                raise ValueError("cross-request event")
        required = api["x-event-data"][event["event"]]["required"]
        if not set(required) <= event["data"].keys():
            raise ValueError("event data missing")
        terminal = event["event"] in ("completed", "error")
    if not terminal:
        raise ValueError("missing terminal event")


def check(require_frozen=False):
    kernel = read_json("kernel_v1.yaml")
    api = read_json("runtime_api_v1.yaml")
    metrics = read_json("metrics_v1.json")
    review = read_json("review_state.json")
    fixture = read_json("examples/runtime_events_v1.json")
    version = kernel["contract_version"]
    assert metrics["contract_version"] == api["info"]["version"] == review["contract_version"] == version
    assert api["components"]["schemas"]["Version"]["const"] == version
    assert version in (ROOT / "contracts/quant_v1.md").read_text(encoding="utf-8")
    assert len(kernel["arguments"]) == 17
    assert kernel["capacity_proposal"]["later_T"] == list(range(2,9))
    assert read_json("examples/b0_handcheck_v1.json")["contract_version"] == version
    assert [a["index"] for a in kernel["arguments"]] == list(range(17))
    assert [a["name"] for a in kernel["arguments"]] == [
        "w_packed", "sw", "xq", "sx", "y", "meta", "T", "N", "K",
        "w_bytes", "sw_bytes", "x_bytes", "sx_bytes", "y_bytes", "meta_bytes", "job_id", "abi_version"]
    assert all(a["type"] == "uint64_t" for a in kernel["arguments"][9:16])
    assert kernel["meta"]["bytes"] == 64
    assert kernel["meta"]["magic"] == int(kernel["meta"]["magic_hex"], 16)
    assert kernel["meta"]["done_success"] == int(kernel["meta"]["done_success_hex"], 16)
    assert [f["offset"] for f in kernel["meta"]["fields"]] == [0,4,8,16,24,28,32,40,48]
    assert set(api["paths"]) == {"/health", "/metrics", "/v1/session", "/v1/chat", "/v1/session/end"}
    def refs(node):
        if isinstance(node, dict):
            if "$ref" in node:
                resolve(api, node["$ref"])
            for child in node.values():
                refs(child)
        elif isinstance(node, list):
            for child in node:
                refs(child)
    refs(api)
    validate(fixture["request"], api["components"]["schemas"]["ChatRequest"], api)
    check_stream(fixture["runtime_events"], fixture["request"], api)
    validate(fixture["application_event"], api["components"]["schemas"]["CheckedSentence"], api)
    assert "sentence_checked" not in api["x-stream-protocol"]["A-events"]
    value = digest()
    if require_frozen:
        if review["status"] != "FROZEN" or review["content_sha256"] != value:
            raise ValueError("Contract is not frozen at this digest")
        for role in "ABC":
            approval = review["approvals"].get(role)
            if not isinstance(approval, dict) or approval.get("decision") != "APPROVED" or approval.get("content_sha256") != value or not approval.get("reviewer") or not approval.get("evidence"):
                raise ValueError(f"Missing independent {role} approval")
    return {"static_checks":"PASS", "verification_level":"PC_TEST", "contract_version":version,
            "content_sha256":value, "review_status":review["status"], "hardware_test":"NOT_TESTED",
            "validator_scope":"Local references, schema subset and static event fixtures; not full OpenAPI conformance or live service tests"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-frozen", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.require_frozen), indent=2, ensure_ascii=False))
    except (AssertionError, KeyError, ValueError) as exc:
        print(json.dumps({"static_checks":"FAIL", "reason":str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
