"""Audit the selected candidate's five actual random-stall RTL batches."""

from collections import Counter
import argparse
import json
import re

from archive_prefill_batches import ROOT, STRESS_COUNTS, case_key, sha, tags


def main(variant):
    expected_log = (ROOT / "logs/b03/stress_split_smoke.log").read_text()
    if "PASS suite=smoke source=synthetic transactions=32" not in expected_log:
        raise RuntimeError("Unsplit 32-case numerical check absent")
    expected = list(tags(expected_log).values())
    actual, batches = [], {}
    for group, count in STRESS_COUNTS.items():
        directory = ROOT / f"evidence/b03/batches/{variant}/stall_{group}"
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest["status"] not in ("PASS_NATIVE", "PASS_RECOVERED", "PASS_POSTCHECK_RECOVERED") or manifest["transactions"] != count or manifest["trace_level"] != "port":
            raise RuntimeError("Incomplete stall batch or missing port trace")
        for name, item in manifest["files"].items():
            if sha(directory / name) != item["sha256"]:
                raise RuntimeError(f"Archived stall evidence changed: {group}/{name}")
        receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8-sig"))
        for name, expected_sha in receipt["input_sha256"].items():
            if sha(ROOT / name).upper() != expected_sha.upper():
                raise RuntimeError(f"Stall source/config fingerprint changed: {name}")
        config = ROOT / f"hls_prefill_{variant}_stall_{group}.cfg"
        if sha(config).upper() != receipt["input_sha256"][config.name].upper():
            raise RuntimeError("Stall config changed")
        content = config.read_text()
        if "cosim.random_stall=1" not in content or "cosim.trace_level=port" not in content:
            raise RuntimeError("Random stall not enabled")
        environment = directory / "verilog/w4a8_linear_v1_subsystem/w4a8_linear_v1_env.sv"
        env = environment.read_text()
        # 总事务延迟仍64；逐通道随机延迟必须出现在实际绑定的BFM类中。
        stall_input = ROOT / "tests/support/prefill_axi_stall.json"
        if sha(stall_input).upper() != receipt["input_sha256"].get("tests/support/prefill_axi_stall.json", "").upper():
            raise RuntimeError("User-stall JSON fingerprint absent or changed")
        configured = json.loads(stall_input.read_text())["port_stall_constraint"]
        channel_constraints, transaction_constraints = {}, {}
        for bus in ("gmem_w", "gmem_sw", "gmem_x", "gmem_y", "gmem_meta", "control"):
            match = re.search(rf"class axi_latency_{bus}\s+extends axi_latency;(.*?)endclass", env, re.DOTALL)
            if not match or f".clatency = lat_{bus};" not in env:
                raise RuntimeError(f"Actual BFM latency class not bound: {bus}")
            functions = dict(re.findall(r"virtual function int get_(\w+)_lat\(\);(.*?)endfunction", match.group(1), re.DOTALL))
            for channel in ("wctrl", "wdata", "wbrsp", "rctrl", "rdata"):
                key = f"{bus} {channel}"
                body = functions.get(channel, "")
                constraint_code = re.sub(r"\s+", "", configured[key])
                span = "[0:3]" if bus == "control" else "[0:7]"
                if "delayinside{" + span + "};" not in constraint_code or "delay==" in constraint_code:
                    raise RuntimeError(f"Channel range is not the frozen finite random span: {key}")
                if constraint_code not in re.sub(r"\s+", "", body) or "std::randomize(delay)" not in body:
                    raise RuntimeError(f"Nonconstant channel constraint not generated: {key}")
                channel_constraints[key] = configured[key]
            if bus != "control":
                for direction in ("wr", "rd"):
                    if re.sub(r"\s+", "", configured[f"{bus} {direction}"]) not in re.sub(r"\s+", "", functions.get(direction, "")):
                        raise RuntimeError(f"Transaction latency not generated: {bus} {direction}")
                    transaction_constraints[f"{bus} {direction}"] = configured[f"{bus} {direction}"]
        modes = re.findall(r".*(?:read|write)_latency_mode.*", env)
        if len(modes) != 10:
            raise RuntimeError("Five AXI masters' read/write latency constraints absent")
        if any("TRANSACTION_FIRST" not in mode for mode in modes):
            raise RuntimeError("Generated AXI latency scheduling mode unrecognized")
        trace_script = (directory / "verilog/w4a8_linear_v1.tcl").read_text()
        if not re.search(r"^\s*log_wave\b", trace_script, re.MULTILINE):
            raise RuntimeError("Actual port waveform logging not enabled")
        waves = [name for name in manifest["files"] if name.endswith(".wdb")]
        if not waves or all(manifest["files"][name]["bytes"] == 0 for name in waves):
            raise RuntimeError("Actual stall port waveform missing")
        actual.extend(manifest["cases"].values())
        batches[group] = {"status": manifest["status"], "transactions": count,
                         "bfm_memory_and_control_channel_constraints": channel_constraints,
                         "bfm_transaction_latency_constraints": transaction_constraints,
                         "bfm_latency_modes": modes,
                         "actual_waveforms": waves, "receipt": manifest["receipt"]}
    if len(actual) != 32 or Counter(map(case_key, expected)) != Counter(map(case_key, actual)):
        raise RuntimeError("Split random-stall coverage changed")
    report = {"stage": "B03", "variant": variant, "status": "PASS", "transactions": 32,
              "split_coverage_matches_unsplit_32": True, "batches": batches,
              "scope": "Actual RTL outputs/meta checked for the generated finite random-stall BFM. Not proof of all AXI schedules or physical DDR."}
    (ROOT / "reports/b03/stress_acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: {variant} five random-stall batches, 32 unchanged RTL transactions with actual port waveforms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=("baseline", "reuse", "double"))
    main(parser.parse_args().variant)
