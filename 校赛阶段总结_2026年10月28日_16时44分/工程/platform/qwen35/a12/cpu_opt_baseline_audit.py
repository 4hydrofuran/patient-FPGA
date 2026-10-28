"""Independent byte/accounting audit of the local A12 CPU step00 freeze."""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_id(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(bytes=path.stat().st_size, sha256=digest)


def audit(out):
    inventory = load(out / "SOURCE_INVENTORY.json")
    baseline = load(out / "BASELINE.json")
    for name, row in inventory["copied"].items():
        path = (out / name).resolve()
        if not path.is_relative_to(out) or file_id(path) != {k: row[k] for k in ("bytes", "sha256")}:
            raise ValueError("Frozen copy mismatch: " + name)
    for name, row in inventory["pinned_assets"].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or file_id(path) != row:
            raise ValueError("External pinned asset mismatch: " + name)
    historical = load(out / "HISTORICAL_PRESERVATION.json")["files"]
    for name, row in historical.items():
        path = (ROOT / row["root"] / name).resolve()
        if not path.is_relative_to(ROOT) or file_id(path) != {k: row[k] for k in ("bytes", "sha256")}:
            raise ValueError("Historical evidence changed: " + name)
    lock = load(ROOT / "contracts/qwen35/contracts.lock")
    for name, digest in lock["files"].items():
        if file_id(ROOT / "contracts/qwen35" / name)["sha256"] != digest:
            raise ValueError("Public contract changed: " + name)
    if hashlib.sha256(json.dumps(lock["files"], sort_keys=True, separators=(",", ":")).encode()).hexdigest() != baseline["contract_sha256"]:
        raise ValueError("Public digest mismatch")
    bundle = out / "frozen/health-bundle"
    manifest = load(bundle / "manifest.json")
    for row in manifest["files"]:
        if file_id(bundle / row["path"]) != {k: row[k] for k in ("bytes", "sha256")}:
            raise ValueError("Package file mismatch: " + row["path"])
    if baseline["package_manifest"] != file_id(bundle / "manifest.json"):
        raise ValueError("Package manifest mismatch")
    for field, name in (("program", "bin/qwen35-a12"), ("cpu_library", "bin/libggml-cpu.so"),
                        ("manager", "control/health_opt_manager.py"),
                        ("window", "platform/qwen35/a12/health_opt_window.py"), ("xclbin", "w4a8.xclbin")):
        if baseline[field] != file_id(bundle / name):
            raise ValueError("Baseline identity mismatch: " + field)
    for item in baseline["timings"]:
        folder = out / "frozen/health-readback/run-v1" / item["backend"] / item["id"]
        clock, result = load(folder / "client-timing.json"), load(folder / "result.json")
        if abs(item["complete_seconds"] - (clock["end_monotonic_ns"] - clock["begin_monotonic_ns"]) / 1e9) > 1e-9:
            raise ValueError("Complete duration mismatch")
        first = clock["token_events"][0]["received_monotonic_ns"]
        if abs(item["first_token_seconds"] - (first - clock["begin_monotonic_ns"]) / 1e9) > 1e-9:
            raise ValueError("First token duration mismatch")
        if result["state_cleared_before_response"] is not True or result["state_position_after_clear"] != -1:
            raise ValueError("Historical result state not cleared")
        if result["request_profile"]["enabled"] != item["profile"]:
            raise ValueError("Plain/profile mixed")
    inputs = load(out / "INPUTS.json")["groups"]
    sizes = dict(health_performance=3, performance_all_workloads=6, development17=17, state_short=13, state_context=3)
    for group, count in sizes.items():
        row = inputs[group]
        path = out / row["frozen_path"]
        requests = load(path)
        if len(requests) != count or file_id(path) != {k: row[k] for k in ("bytes", "sha256")}:
            raise ValueError("Input group changed: " + group)
    for row in load(out / "CANDIDATES.json")["candidates"]:
        if row["status"] != "RESERVED_NOT_IMPLEMENTED":
            raise ValueError("Unexpected implementation claim")
        if any(not (out / row[k]).is_dir() or any((out / row[k]).iterdir()) for k in ("source", "build", "package")):
            raise ValueError("Step00 candidate area is not empty")
    if baseline["new_optimization_results"] is not None or baseline["default_FPGA_enabled"] is not False:
        raise ValueError("Unexpected performance/default claim")
    if baseline["A12_step11"] != "PENDING" or baseline["domains"]["new_BOARD"] != "NOT_TESTED":
        raise ValueError("Unexpected stage/board claim")
    for name in ("contracts_01.json", "config_01.json", "freeze_01.json"):
        if load(out / "logs" / name)["exit_code"] != 0:
            raise ValueError("Required command failed: " + name)
    return dict(status="PASS_LOCAL_INDEPENDENT_INTEGRITY_AND_ACCOUNTING", domain="LOCAL_FILES_NO_MODEL",
                frozen_copies=len(inventory["copied"]), external_assets=len(inventory["pinned_assets"]),
                preserved_health_files=len(historical), input_groups=sizes, timing_rows=len(baseline["timings"]),
                new_BOARD="NOT_TESTED", new_cross_build="NOT_TESTED", new_performance_results=None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.out.resolve()), indent=2))
