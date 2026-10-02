"""Archive completed native Cosim batches and compare the same 34 RTL calls."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("baseline", "reuse", "double")
GROUPS = ("smoke", "gate_t1", "gate_t8", "down_t1", "down_t8")
STRESS_COUNTS = {"basic": 12, "lifecycle": 11, "tail": 7, "max_k": 1, "max_n": 1}


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            value.update(chunk)
    return value.hexdigest()


def receipt(variant: str, step: str) -> tuple[Path, dict]:
    for path in reversed(sorted((ROOT / "reports/b03" / variant).glob(f"*/{step}.receipt.json"))):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if data["exit_code"] == 0:
            return path, data
    raise RuntimeError(f"Missing successful {variant}/{step}")


def tags(log: str) -> dict[int, dict]:
    result = {}
    for index, name, tokens, outputs, inputs, job in re.findall(
        r"TRANSACTION index=(\d+) case=(\S+) T=(\d+) N=(\d+) K=(\d+) job=(\d+)", log
    ):
        entry = {"case": name, "T": int(tokens), "N": int(outputs), "K": int(inputs), "job": int(job)}
        number = int(index)
        if number in result and result[number] != entry:
            raise RuntimeError("Conflicting pre/postcheck transaction tags")
        result[number] = entry
    return result


def update_progress() -> None:
    status_path = ROOT / "PROJECT_STATUS.json"
    status = json.loads(status_path.read_text(encoding="utf-8-sig"))
    counts = {}
    for variant in VARIANTS:
        counts[variant] = sum(json.loads(p.read_text())["transactions"]
                              for group in GROUPS
                              if (p := ROOT / "evidence/b03/batches" / variant / group / "manifest.json").exists())
        status["b03_variants"][variant]["cosim"] = "PASS_34_NOMINAL_CALLS" if counts[variant] == 34 else f"IN_PROGRESS_{counts[variant]}_OF_34"
    status["updated_at"] = datetime.now().astimezone().isoformat()
    status["domain_scope"] = f"B03 actual serial nominal RTL accepted {sum(counts.values())}/102 calls; selected random-stall acceptance and delivery pending."
    status["b03_progress"].update({"nominal_passed_calls_by_variant": counts,
                                 "baseline_rtl_passed_calls": counts["baseline"],
                                 "active": "Serial runner; see newest logs/b03 receipt"})
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def archive(variant: str, group: str) -> None:
    stress = group == "stall" or group.startswith("stall_")
    step = "stall_cosim" if group == "stall" else "stall_cosim_" + group[6:] if stress else f"cosim_{group}"
    recovered = False
    postonly = False
    extra = {}
    try:
        rp, data = receipt(variant, step)
        log = (ROOT / data["log"]).read_text(encoding="utf-8", errors="replace")
        if "C/RTL co-simulation finished: PASS" not in log:
            raise RuntimeError("Native PASS absent")
    except RuntimeError:
        recovered = True
        try:
            rp, data = receipt(variant, step + "_postcheck_only")
            postonly = True
        except RuntimeError:
            rp, data = receipt(variant, step + "_postcheck")
        if postonly:
            snapshot = rp.parent / f"{step}_postcheck_only_proof.json"
            prepared = json.loads(snapshot.read_text(encoding="utf-8-sig"))
            if not prepared["rtl_completed_by_native_logs"] or prepared["postcompile_exit_code"] or prepared["postcheck_exit_code"]:
                raise RuntimeError("Completed native RTL / postcheck-only proof incomplete")
            for name, expected in prepared["rtl_evidence_sha256"].items():
                if sha(ROOT / name).upper() != expected.upper():
                    raise RuntimeError("Actual completed RTL evidence changed")
            compile_log = ROOT / prepared["postcompile_log"]
            if "POST_CHECK" not in compile_log.read_text(errors="replace"):
                raise RuntimeError("Explicit POST_CHECK flag absent")
            extra["postcompile.log"] = compile_log
        else:
            for suffix in ("relink", "rtl"):
                path = rp.parent / f"{step}_{suffix}.receipt.json"
                entry = json.loads(path.read_text(encoding="utf-8-sig"))
                if entry["exit_code"] != 0:
                    raise RuntimeError(f"Recovery {suffix} failed")
                extra[f"{suffix}.receipt.json"] = path
                extra[f"{suffix}.log"] = ROOT / entry["log"]
            postcompile = rp.parent / f"{step}_postcompile.receipt.json"
            if postcompile.exists():
                compiled = json.loads(postcompile.read_text(encoding="utf-8-sig"))
                compile_log = ROOT / compiled["log"]
                if compiled["exit_code"] != 0 or "POST_CHECK" not in compile_log.read_text(errors="replace"):
                    raise RuntimeError("Explicit postchecker compile proof missing")
                extra["postcompile.receipt.json"] = postcompile
                extra["postcompile.log"] = compile_log
            snapshot = rp.parent / f"{step}_snapshot.json"
            prepared = json.loads(snapshot.read_text(encoding="utf-8-sig"))
        native_path = ROOT / prepared["prepared_receipt"]
        native = json.loads(native_path.read_text(encoding="utf-8-sig"))
        extra["native_failed.receipt.json"] = native_path
        extra["native_failed.log"] = ROOT / native["log"]
        extra["snapshot.json"] = snapshot
        log = (ROOT / native["log"]).read_text(encoding="utf-8", errors="replace")
        log += (ROOT / data["log"]).read_text(encoding="utf-8", errors="replace")
    for name, expected in data["input_sha256"].items():
        if sha(ROOT / name).upper() != expected.upper():
            raise RuntimeError(f"Source/config changed during verification: {name}")
    suite = "smoke" if group in ("smoke", "stall") else "stress_" + group[6:] if stress else "b03_" + group
    count = 32 if group == "stall" else STRESS_COUNTS[group[6:]] if stress else 30 if group == "smoke" else 1
    if not re.search(
        rf"B03 PASS suite={suite} source=synthetic transactions={count}\b", log
    ):
        raise RuntimeError("Native Cosim or output postcheck PASS missing")
    sim = ROOT / f"build/b03_{variant}_hls/hls/sim"
    performance = sim / "verilog/w4a8_linear_v1.performance.result.transaction.xml"
    timing = native if postonly else entry if recovered else data
    started = datetime.fromisoformat(timing["finished_at_utc"].replace("Z", "+00:00")) - timedelta(seconds=timing["elapsed_seconds"])
    if performance.stat().st_mtime + 2 < started.timestamp():
        raise RuntimeError("Stale RTL performance file")
    for output in (sim / "tv/rtldatafile").glob("rtl.*.dat"):
        if output.stat().st_mtime + 2 < started.timestamp():
            raise RuntimeError(f"Stale actual RTL output: {output.name}")
    cycles = {int(i): int(n) for i, n in re.findall(r"transaction\s+(\d+):\s+(\d+)", performance.read_text())}
    cases = tags(log)
    if set(cycles) != set(range(count)) or set(cases) != set(cycles):
        raise RuntimeError("Incomplete RTL transaction/performance set")
    for index, case in cases.items():
        case["cycles"] = cycles[index]
    dest = ROOT / "evidence/b03/batches" / variant / group
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / "manifest.json").exists():
        raise RuntimeError("Refusing to replace an archived successful batch")
    sources = list(sim.glob("tv/cdatafile/*")) + list(sim.glob("tv/rtldatafile/*"))
    sources += list(sim.glob("verilog/*.wdb"))
    sources += [performance, sim / "verilog/run_xsim.bat", sim / "verilog/w4a8_linear_v1.tcl"]
    if postonly:
        sources += [sim / "verilog/xsim.log", sim / "verilog/xsim.dir/w4a8_linear_v1/xsimkernel.log"]
    if not recovered:
        sources += [sim / "report/w4a8_linear_v1_cosim.rpt"]
    if stress:
        sources += list(sim.glob("verilog/axivip/*.sv")) + list(sim.glob("verilog/svtb/*.sv"))
        sources += list(sim.glob("verilog/w4a8_linear_v1_subsystem/*.sv"))
    files = {}
    for source in sources:
        if not source.is_file():
            raise RuntimeError(f"Evidence missing: {source}")
        relative = source.relative_to(sim)
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files[str(relative).replace("\\", "/")] = {"bytes": target.stat().st_size, "sha256": sha(target)}
    for name, source in {"cosim.log": ROOT / data["log"], "receipt.json": rp,
                         "csynth.rpt": sim.parent / "syn/report/csynth.rpt", "kernel.xml": sim.parent / "kernel.xml", **extra}.items():
        shutil.copy2(source, dest / name)
        files[name] = {"bytes": (dest / name).stat().st_size, "sha256": sha(dest / name)}
    # 原生失败码保留；恢复PASS只来自本次RTL和实际输出回放的各自退出0。
    (dest / "combined_tags.log").write_text(log, encoding="utf-8")
    files["combined_tags.log"] = {"bytes": (dest / "combined_tags.log").stat().st_size, "sha256": sha(dest / "combined_tags.log")}
    rtl_log = log if postonly else (ROOT / entry["log"]).read_text(errors="replace") if recovered else log
    memory = re.search(r"xsimkernel Simulation Memory Usage:.*?Peak:\s*([\d,]+)", rtl_log)
    manifest = {"status": "PASS_POSTCHECK_RECOVERED" if postonly else "PASS_RECOVERED" if recovered else "PASS_NATIVE", "variant": variant, "group": group,
                "receipt": str(rp.relative_to(ROOT)).replace("\\", "/"),
                "trace_level": "port" if stress else "none",
                "transactions": count, "cases": cases, "files": files,
                "execution": {"elapsed_seconds": data["elapsed_seconds"],
                              "recovered_rtl_elapsed_seconds": entry["elapsed_seconds"] if recovered and not postonly else None,
                              "xsim_peak_memory_KB": int(memory.group(1).replace(",", "")) if memory else None}}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    update_progress()
    print(f"Archived {variant}/{group}: {count} RTL transactions {manifest['status']}")


def case_key(case: dict) -> tuple:
    return tuple(case[key] for key in ("case", "T", "N", "K"))


def summarize() -> None:
    results = {}
    for variant in VARIANTS:
        all_cases = []
        targets = {}
        batch_receipts = []
        for group in GROUPS:
            dest = ROOT / "evidence/b03/batches" / variant / group
            manifest = json.loads((dest / "manifest.json").read_text())
            for name, item in manifest["files"].items():
                if sha(dest / name) != item["sha256"]:
                    raise RuntimeError(f"Archived evidence modified: {variant}/{group}/{name}")
            all_cases.extend(manifest["cases"].values())
            batch_receipts.append(manifest["receipt"])
            if group != "smoke":
                value = next(iter(manifest["cases"].values()))
                targets[value["case"]] = {**value, "cycles_per_token": value["cycles"] / value["T"]}
        native_path, native = receipt(variant, "native_test")
        full = tags((ROOT / native["log"]).read_text())
        expected = [c for index, c in full.items() if index < 30 or
                    (c["case"].startswith("qwen35_") and c["T"] in (1, 8))]
        if len(expected) != 34 or Counter(map(case_key, expected)) != Counter(map(case_key, all_cases)):
            raise RuntimeError(f"Split RTL coverage changed: {variant}")
        lines = (ROOT / f"evidence/b03/batches/{variant}/smoke/csynth.rpt").read_text().splitlines()
        row = next(line for line in lines if line.startswith("|+ w4a8_linear_v1 "))
        fields = [part.strip() for part in row.split("|")]
        synth = {"clock_slack_ns_estimate": float(fields[10]), "bram18k_estimate": int(fields[11].split()[0]),
                 "dsp_estimate": int(fields[12].split()[0]), "ff_estimate": int(fields[13].split()[0]),
                 "lut_estimate": int(fields[14].split()[0]),
                 "dataflow_task_detected": any("prefill_overlap*" in line and "dataflow" in line for line in lines)}
        receipts = {step: str(receipt(variant, step)[0].relative_to(ROOT)).replace("\\", "/")
                    for step in ("native_test", "real_test", "csim", "synth")}
        results[variant] = {"synthesis": synth, "rtl_transactions": len(all_cases),
                            "split_coverage_matches_original": True, "targets": targets,
                            "receipts": receipts, "cosim_batch_receipts": batch_receipts}
    for variant in ("reuse", "double"):
        for name, case in results[variant]["targets"].items():
            before = results["baseline"]["targets"][name]["cycles"]
            case["change_vs_baseline_cycles"] = case["cycles"] - before
            case["improvement_percent"] = (before - case["cycles"]) * 100 / before
    output = {"stage": "B03", "status": "ALL_NOMINAL_RTL_PASS", "clock_target_ns": 6.667,
              "tool": "Vitis HLS 2026.1 / actual XSIM with native or recovered postcheck", "measurements": results,
              "algorithm_request_bytes_T8": {"weight_matrix": 1835008, "baseline_weight_including_prescan": 16515072,
                  "reuse_weight_including_prescan": 3670016, "baseline_scales": 917504, "reuse_scales": 114688,
                  "measured_bus_bytes": None},
              "limits": ["Nominal XSIM cycles, not physical DDR or board service time.",
                         "Resources/slack are HLS estimates; implementation/ARM/BOARD NOT_TESTED.",
                         "INT32 partial checks inspect the C++ helper; RTL output/meta checked by native postcheck.",
                         "Real tensors are two layer0 weights with synthetic activations, PC only."]}
    path = ROOT / "reports/b03/ablation.json"
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({v: r["targets"] for v, r in results.items()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", nargs=2, metavar=("VARIANT", "GROUP"))
    args = parser.parse_args()
    if args.archive:
        variant, group = args.archive
        if variant not in VARIANTS or group not in (*GROUPS, "stall", *("stall_" + g for g in STRESS_COUNTS)):
            raise SystemExit("Unsupported variant/group")
        archive(variant, group)
    else:
        summarize()
