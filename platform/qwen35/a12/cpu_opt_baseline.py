"""Freeze A12 CPU step00 locally. Does not import a runtime or access a board."""
import argparse
import datetime
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[3]
HEALTH = ROOT / "evidence/model_pl_A/20261024-health-opt-v1"
BUNDLE = HEALTH / "candidate/bundle-v1"
READBACK = HEALTH / "candidate/readback-v1"
STEP10 = ROOT / "evidence/model_pl_A/20261024-step10-v1"
CONTRACT = "83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def safe(root, name):
    if not isinstance(name, str) or "\\" in name or ":" in name:
        raise ValueError("Invalid relative path")
    if PurePosixPath(name).is_absolute() or any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError("Unsafe relative path")
    root = root.resolve()
    path = root.joinpath(*name.split("/"))
    if not path.resolve().is_relative_to(root):
        raise ValueError("Path escaped root")
    if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)):
        raise ValueError("Symlink in frozen input")
    return path


def identity(path):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Input changed during read: " + str(path))
    return dict(bytes=after.st_size, sha256=digest.hexdigest())


def verify_map(root, mapping):
    rows = {}
    for name, expected in mapping.items():
        actual = identity(safe(root, name))
        pin = dict(sha256=expected) if isinstance(expected, str) else expected
        if any(actual[k] != pin[k] for k in ("bytes", "sha256") if k in pin):
            raise ValueError("Frozen identity mismatch: " + str(root / name))
        rows[name] = actual
    return rows


def freeze(out):
    # Entry requires separately recorded protection checks, in this order.
    for name in ("contracts_01.json", "config_01.json"):
        if read(out / "logs" / name)["exit_code"] != 0:
            raise ValueError("Protection check did not pass: " + name)
    if not (out / "START.json").is_file():
        raise ValueError("Missing initial worktree capture")
    (out / "frozen").mkdir(exist_ok=False)
    copied = {}
    sources = {}

    def copy(src, target):
        src = src.resolve()
        relative = src.relative_to(ROOT).as_posix()
        source_id = identity(src)
        dst = safe(out, target)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with src.open("rb") as incoming, dst.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        if identity(dst) != source_id or identity(src) != source_id:
            raise ValueError("Copy changed: " + relative)
        copied[target] = dict(source=relative, **source_id)
        sources[relative] = source_id

    package = read(HEALTH / "PACKAGE.json")
    if identity(BUNDLE / "manifest.json")["sha256"] != package["manifest_sha256"]:
        raise ValueError("Health package pin mismatch")
    manifest = read(BUNDLE / "manifest.json")
    if manifest["contract_sha256"] != CONTRACT:
        raise ValueError("Health package contract mismatch")
    bundle_rows = verify_map(BUNDLE, {r["path"]: r for r in manifest["files"]})
    health_seal = verify_map(HEALTH, read(HEALTH / "SEAL.json")["files"])
    readback_rows = verify_map(READBACK, read(HEALTH / "candidate/READBACK_FILES.json"))
    if identity(READBACK / "manifest.json") != identity(BUNDLE / "manifest.json"):
        raise ValueError("Deployed/readback package mismatch")
    assets = verify_map(ROOT, read(BUNDLE / "control/asset-pins.json"))
    sources.update(assets)  # Large model/sidecar payloads stay in place; pinned, not duplicated.
    for name in ["manifest.json", *bundle_rows]:
        copy(safe(BUNDLE, name), "frozen/health-bundle/" + name)
    for name in readback_rows:
        copy(safe(READBACK, name), "frozen/health-readback/" + name)
    for name in ("SEAL.json", "PACKAGE.json", "SUMMARY.json", "BOARD_AUDIT.json", "REPORT.md", "FAILURES.json", "DERIVATION.json"):
        copy(HEALTH / name, "frozen/health-records/" + name)

    request_files = {
        "health_performance": BUNDLE / "control/requests.json",
        "performance_all_workloads": STEP10 / "optimized/bundle-v1/control/requests.json",
        "development17": ROOT / "evidence/model_pl_A/20261024-step08-v1/generation/bundle-v1/control/requests.json",
        "state_short": ROOT / "evidence/model_pl_A/20261024-step09-v1/short/bundle-v1/control/requests.json",
        "state_context": ROOT / "evidence/model_pl_A/20261024-step09-v1/context/bundle-v1/control/requests.json",
    }
    expected_sizes = dict(health_performance=3, performance_all_workloads=6, development17=17, state_short=13, state_context=3)
    inputs = {}
    for group, path in request_files.items():
        rows = read(path)
        if len(rows) != expected_sizes[group] or len({r["id"] for r in rows}) != len(rows):
            raise ValueError("Request inventory mismatch: " + group)
        target = "frozen/inputs/" + group + ".json"
        copy(path, target)
        inputs[group] = dict(source=path.relative_to(ROOT).as_posix(), frozen_path=target,
                             **identity(path), requests=[dict(id=r["id"], op=r["op"],
                                 prompt_tokens=len(r.get("tokens", [])),
                                 teacher_tokens=len(r.get("teacher_tokens", [])),
                                 max_tokens=r.get("max_tokens"), prefill_chunk=r.get("prefill_chunk"),
                                 logits_mode=r.get("logits_mode"), profile=r.get("profile", False),
                                 cache_policy=r.get("cache_policy", "R0_DEFAULT")) for r in rows])
    work = {r["id"]: r for r in read(request_files["performance_all_workloads"])}
    if [len(work[n]["tokens"]) for n in ("short_plain", "natural_plain", "context128_profile", "context1024_profile")] != [9, 107, 128, 1022]:
        raise ValueError("Performance workload changed")
    for r in read(request_files["health_performance"]):
        if r != work[r["id"]]:
            raise ValueError("Health workload differs from task10")
    write(out / "INPUTS.json", dict(schema="A12_CPU_OPT_INPUTS_V1", groups=inputs,
        teacher_vs_natural="teacher_tokens nonempty = fixed trajectory; natural requests remain greedy with EOS",
        physical_T_max=8, context=1024, reset_policy="R0", new_execution="NOT_TESTED",
        warning="Frozen historical requests/configs carry no current authorization or lease."))

    # Scope is A-owned CPU/manager inputs only; do not recurse into peer or audio projects.
    current_paths = ["AGENTS.md", "docs/PROJECT_STATUS.json", "docs/status/A.md", "docs/DESIGN_GAP.md",
        "docs/DECISIONS.md", "docs/TEST_MATRIX.md", "docs/AI_ASSISTANCE.md",
        "docs/A12_CPU_OPTIMIZATION_PLAN_20261024.md", "docs/A12_STEP_PLAN_20261023.md",
        "docs/handoffs/A12_CPU_OPT_CROSS_CHAT_HANDOFF_20261024.md",
        "config/qwen35/selection.json", "config/qwen35/deploy.pc.json", "platform/toolchain.lock.json",
        "models/model.lock.json", "runtime/qwen35_w4a8/sp-hook.cpp", "runtime/qwen35_w4a8/sp-hook.h",
        "runtime/qwen35_w4a8/cpu_backend.cpp", "runtime/qwen35_w4a8/tiled_simd.hpp",
        "platform/qwen35/a12/health_opt.py", "platform/qwen35/a12/health_opt_derive.py",
        "platform/qwen35/a12/health_opt_package.py", "platform/qwen35/a12/health_opt_audit.py",
        "platform/qwen35/a12/health_opt_closeout.py", "platform/qwen35/a12/step10_window.py",
        "platform/qwen35/a12/step10_manager.py", "platform/qwen35/a12/step10_supervisor.py",
        "platform/qwen35/a12/cpu_opt_baseline.py"]
    for name in current_paths:
        copy(safe(ROOT, name), "frozen/worktree/" + name)
    extra_paths = set()
    for directory in ("platform/qwen35/a12", "runtime/qwen35_w4a8/a12", "modules/linear_A", "contracts/qwen35"):
        extra_paths.update(p for p in (ROOT / directory).rglob("*")
                           if p.is_file() and "__pycache__" not in p.parts
                           and p.suffix in (".py", ".cpp", ".c", ".h", ".hpp", ".sh", ".ps1", ".json", ".jsonl", ".lock", ".md", ".txt", ".map"))
    for path in sorted(extra_paths):
        relative = path.relative_to(ROOT).as_posix()
        if "frozen/worktree/" + relative not in copied:
            copy(path, "frozen/worktree/" + relative)
    provenance = [STEP10 / "LLAMA_DERIVATION.json", STEP10 / "BUILD-v2.json", STEP10 / "FAILURES.json",
        STEP10 / "build-logs/ggml-cpu-timing.c", ROOT / "evidence/model_pl_A/20261024-cpu-opt-plan-v1/BASELINE_EXTRACT.json",
        ROOT / "evidence/model_pl_A/20261024-step09-v1/STATE_MATRIX.md",
        ROOT / "evidence/model_pl_A/20261024-step09-v1/SHORT_AUDIT.json",
        ROOT / "evidence/model_pl_A/20261024-step09-v1/CONTEXT_AUDIT.json",
        ROOT / "evidence/model_pl_A/20261024-step08-v1/REPORT.md",
        ROOT / "evidence/model_pl_A/20261024-cpu-peer-handoff-v1/PUBLISHED.json"]
    for path in provenance:
        copy(path, "frozen/provenance/" + path.relative_to(ROOT).as_posix())

    timings = []
    for side in ("s1", "s2"):
        for r in read(request_files["health_performance"]):
            base = READBACK / "run-v1" / side / r["id"]
            timing, result = read(base / "client-timing.json"), read(base / "result.json")
            if read(base / "request.json") != r or result["status"] != "OK":
                raise ValueError("Readback request/result mismatch")
            if result["prompt_tokens"] != len(r["tokens"]):
                raise ValueError("Readback workload/EOS mismatch")
            teacher = bool(r.get("teacher_tokens"))
            if result["teacher_forced"] != teacher or (not teacher and not result["eos"]):
                raise ValueError("Teacher/natural completion mismatch")
            if abs(timing["result_wall_ms"] - (timing["end_monotonic_ns"] - timing["begin_monotonic_ns"]) / 1e6) > 1e-5:
                raise ValueError("Client clock accounting mismatch")
            timings.append(dict(backend=side, id=r["id"], profile=r.get("profile", False),
                first_token_seconds=timing["first_token_wall_ms"] / 1000,
                complete_seconds=timing["result_wall_ms"] / 1000,
                prefill_seconds=result["prefill_ms"] / 1000,
                decode_seconds=result["decode_ms"] / 1000, prompt_tokens=result["prompt_tokens"],
                output_tokens=result["output_tokens"], eos=result["eos"], text=result["text"],
                prefill_logits_fnv64=result["last_prompt_logits_fnv64"],
                source=(base / "client-timing.json").relative_to(ROOT).as_posix()))
    for r in read(request_files["health_performance"]):
        pair = [t for t in timings if t["id"] == r["id"]]
        for key in ("output_tokens", "eos", "text", "prefill_logits_fnv64"):
            if pair[0][key] != pair[1][key]:
                raise ValueError("Historical S1/S2 pair mismatch: " + key)
    runtime_profile = read(READBACK / "run-v1/s2/runtime-profile.json")
    if runtime_profile["xclbin_sha256"] != identity(BUNDLE / "w4a8.xclbin")["sha256"]:
        raise ValueError("Runtime xclbin identity mismatch")
    if read(READBACK / "run-v1/s2/identity.json")["binary_sha256"] != identity(BUNDLE / "bin/qwen35-a12")["sha256"]:
        raise ValueError("Runtime binary identity mismatch")
    lock = read(ROOT / "models/model.lock.json")
    lineage = read(STEP10 / "LLAMA_DERIVATION.json")
    protected = {name: dict(root=HEALTH.relative_to(ROOT).as_posix(), **row) for name, row in health_seal.items()}
    write(out / "HISTORICAL_PRESERVATION.json", dict(status="PASS_LOCAL_BYTES", files=protected))
    write(out / "SOURCE_INVENTORY.json", dict(copied=copied, pinned_assets=assets))
    write(out / "BASELINE.json", dict(schema="A12_CPU_OPT_BASELINE_V1",
        status="PASS_LOCAL_BASELINE_FROZEN_EXISTING_BOARD_EVIDENCE_ONLY",
        created_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        baseline="20261024-health-opt-v1", model=lock["model"], model_revision=lock["revision"],
        runtime_commit=lock["runtime_commit"], runtime_derivation=lineage, contract_sha256=CONTRACT,
        program=identity(BUNDLE / "bin/qwen35-a12"), cpu_library=identity(BUNDLE / "bin/libggml-cpu.so"),
        manager=identity(BUNDLE / "control/health_opt_manager.py"),
        window=identity(BUNDLE / "platform/qwen35/a12/health_opt_window.py"),
        xclbin=identity(BUNDLE / "w4a8.xclbin"), package_manifest=identity(BUNDLE / "manifest.json"),
        actual_configs=["frozen/health-readback/run-v1/s2/runtime-" + n + ".json" for n in ("backend", "profile", "route")],
        timings=timings, historical_board_identity=dict(boot_id=runtime_profile["boot_id"],
            freshness="HISTORICAL_ONLY_NOT_A_NEW_GATE", kernel_build_id=runtime_profile["kernel_build_id"]),
        domains=dict(local_integrity="PASS", new_PC_model_run="NOT_TESTED", new_cross_build="NOT_TESTED",
            new_BOARD="NOT_TESTED", health_context1024="NOT_TESTED"),
        default_FPGA_enabled=False, A12_step11="PENDING", new_optimization_results=None,
        hardware_cycles=None, power_watts=None, actual_model_settings="unknown", subagents=0,
        source_authority="Actual health package/readback manifest; earlier DERIVATION hashes are historical intermediate values.",
        worktree_snapshot_scope="Tracked worktree/index patches plus A12 CPU/management/contract source copies; unrelated projects and large model payloads not duplicated."))
    # Reserve separate work areas for all A candidates. No payload is executable yet.
    candidates = []
    for name in ("01B", "02", "04", "05", "06", "07", "08"):
        workspace = out / "candidates" / name
        for part in ("source", "build", "package"):
            (workspace / part).mkdir(parents=True, exist_ok=False)
        item = dict(id=name, maintainer="A", status="RESERVED_NOT_IMPLEMENTED",
                    source=str((workspace / "source").relative_to(out).as_posix()),
                    build=str((workspace / "build").relative_to(out).as_posix()),
                    package=str((workspace / "package").relative_to(out).as_posix()),
                    rollback="frozen/health-bundle", historical_permission_reusable=False)
        write(workspace / "CANDIDATE.json", item)
        candidates.append(item)
    write(out / "CANDIDATES.json", dict(candidates=candidates,
        peer=dict(tasks=["01A", "03"], plan_received="USER_CONFIRMED", candidate_received=False),
        recovery="Select frozen health bundle only after a new reviewed window, fresh gates, unique lease; never replay old launch/review/lease files.",
        cpu_default="Existing default CPU selection; no automatic deployment or backend change."))
    print(json.dumps(dict(status="FROZEN_LOCAL", bundle_files=len(bundle_rows), readback_files=len(readback_rows),
                          assets=len(assets), health_seal_files=len(health_seal), frozen_copies=len(copied))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / "evidence/model_pl_A"):
        parser.error("Output must stay in A model evidence")
    freeze(out)


if __name__ == "__main__":
    main()
