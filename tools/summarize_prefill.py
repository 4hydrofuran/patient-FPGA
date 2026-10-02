"""Summarize B03 tool receipts and archive nominal RTL evidence before stress runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("baseline", "reuse", "double")


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_receipt(variant: str, step: str) -> tuple[Path, dict]:
    paths = sorted((ROOT / "reports/b03" / variant).glob(f"*/{step}.receipt.json"))
    for path in reversed(paths):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if data["exit_code"] == 0:
            return path, data
    raise RuntimeError(f"No successful {variant} {step} receipt")


def archive_nominal(variant: str) -> dict:
    receipt_path, receipt = latest_receipt(variant, "cosim")
    destination = ROOT / "evidence/b03/ablation_raw" / variant
    project = ROOT / f"build/b03_{variant}_hls/hls"
    files = {
        "csynth.rpt": project / "syn/report/csynth.rpt",
        "performance.xml": project / "sim/verilog/w4a8_linear_v1.performance.result.transaction.xml",
        "cosim.log": ROOT / receipt["log"],
        "kernel.xml": project / "kernel.xml",
        "cosim_report.rpt": project / "sim/report/w4a8_linear_v1_cosim.rpt",
    }
    destination.mkdir(parents=True, exist_ok=True)
    # Never replace nominal measurements with a later random-stall run.
    manifest_path = destination / "manifest.json"
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, expected in saved["sha256"].items():
            if fingerprint(destination / name) != expected:
                raise RuntimeError(f"Archived evidence changed: {name}")
        return saved
    raw_destination = ROOT / "evidence/b03" / f"rtl_nominal_{variant}"
    raw_destination.mkdir(parents=True, exist_ok=True)
    raw_hashes = {}
    raw_sources = list(project.glob("sim/tv/rtldatafile/*")) + list(project.glob("sim/verilog/*.wdb"))
    for source in raw_sources:
        if not source.is_file():
            continue
        target = raw_destination / source.name
        shutil.copy2(source, target)
        raw_hashes[source.name] = {"bytes": target.stat().st_size, "sha256": fingerprint(target)}
    raw_manifest = {"variant": variant, "scope": "actual nominal RTL outputs and available port waveform", "files": raw_hashes}
    (ROOT / f"reports/b03/{variant}/rtl_evidence.json").write_text(json.dumps(raw_manifest, indent=2) + "\n", encoding="utf-8")
    hashes = {}
    for name, source in files.items():
        if not source.is_file():
            raise RuntimeError(f"Missing tool evidence: {source}")
        shutil.copy2(source, destination / name)
        hashes[name] = fingerprint(destination / name)
    manifest = {"variant": variant, "cosim_receipt": str(receipt_path.relative_to(ROOT)).replace("\\", "/"), "sha256": hashes}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def measurements(variant: str) -> dict:
    archive_nominal(variant)
    directory = ROOT / "evidence/b03/ablation_raw" / variant
    lines = (directory / "csynth.rpt").read_text(encoding="utf-8").splitlines()
    row = next(line for line in lines if line.startswith("|+ w4a8_linear_v1 "))
    fields = [part.strip() for part in row.split("|")]
    synthesis = {
        "clock_slack_ns_estimate": float(fields[10]),
        "bram18k_estimate": int(fields[11].split()[0]),
        "dsp_estimate": int(fields[12].split()[0]),
        "ff_estimate": int(fields[13].split()[0]),
        "lut_estimate": int(fields[14].split()[0]),
        "dataflow_task_detected": any("prefill_overlap*" in line and "dataflow" in line for line in lines),
    }
    log = (directory / "cosim.log").read_text(encoding="utf-8", errors="replace")
    if "C/RTL co-simulation finished: PASS" not in log:
        raise RuntimeError(f"Cosim PASS absent: {variant}")
    tags = {}
    for index, case, tokens, outputs, inputs, job in re.findall(
        r"TRANSACTION index=(\d+) case=(\S+) T=(\d+) N=(\d+) K=(\d+) job=(\d+)", log
    ):
        value = {"case": case, "T": int(tokens), "N": int(outputs), "K": int(inputs), "job": int(job)}
        number = int(index)
        if number in tags and tags[number] != value:
            raise RuntimeError(f"Transaction mapping conflict: {variant} {number}")
        tags[number] = value
    performance = (directory / "performance.xml").read_text(encoding="utf-8")
    cycles = {int(index): int(latency) for index, latency in re.findall(r"transaction\s+(\d+):\s+(\d+)", performance)}
    if set(tags) != set(cycles) or set(tags) != set(range(34)):
        raise RuntimeError(f"Incomplete nominal RTL transaction set: {variant}: {len(tags)}, {len(cycles)}")
    targets = {}
    for index, value in tags.items():
        if value["case"].startswith("qwen35_"):
            targets[value["case"]] = {**value, "transaction": index, "cycles": cycles[index], "cycles_per_token": cycles[index] / value["T"]}
    if len(targets) != 4:
        raise RuntimeError("Expected both target shapes T1/T8")
    receipts = {}
    for step in ("native_test", "real_test", "csim", "synth", "cosim"):
        path, data = latest_receipt(variant, step)
        receipts[step] = str(path.relative_to(ROOT)).replace("\\", "/")
    return {"synthesis": synthesis, "rtl_transactions": len(cycles), "targets": targets, "receipts": receipts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-only", choices=VARIANTS)
    args = parser.parse_args()
    if args.archive_only:
        archive_nominal(args.archive_only)
        print(f"Archived {args.archive_only} nominal evidence")
        return
    results = {variant: measurements(variant) for variant in VARIANTS}
    for variant in ("reuse", "double"):
        for case, value in results[variant]["targets"].items():
            before = results["baseline"]["targets"][case]["cycles"]
            value["change_vs_baseline_cycles"] = value["cycles"] - before
            value["improvement_percent"] = (before - value["cycles"]) * 100.0 / before
    requests = {}
    for tokens in (1, 8):
        weight_bytes = 3584 * 1024 // 2
        scale_bytes = 3584 * (1024 // 128) * 4
        requests[f"T{tokens}"] = {
            "weight_bytes_per_matrix": weight_bytes,
            "baseline_weight_reads_including_prescan": (tokens + 1) * weight_bytes,
            "reuse_weight_reads_including_prescan": 2 * weight_bytes,
            "baseline_scale_reads": tokens * scale_bytes,
            "reuse_scale_reads": scale_bytes,
            "measured_bus_bytes": None,
        }
    output = {
        "stage": "B03", "tool": "Vitis HLS 2026.1 / XSIM", "clock_target_ns": 6.667,
        "measurements": results, "algorithm_request_bytes": requests,
        "limits": [
            "Cycles are nominal XSIM results, not measured DDR or board service times.",
            "HLS resources/slack are estimates; implementation and board remain NOT_TESTED.",
            "INT32 partial checks observe the C++ MAC helper, not internal RTL partial-sum registers.",
            "Real tensors cover two layer0 weights with synthetic activations, PC only.",
        ],
    }
    path = ROOT / "reports/b03/ablation.json"
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
