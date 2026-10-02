"""Prove the explicit POST_CHECK binary consumes archived actual RTL outputs."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "build/b03_baseline_hls/hls/sim/wrapc_pc/cosim.pc.exe"
DESTINATION = ROOT / "build/b03_postcheck_audit"


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    environment = os.environ.copy()
    environment["PATH"] = ";".join(("D:/2026.1/2026.1/win64/lib/csim",
        "D:/2026.1/2026.1/Vitis/tps/mingw/10.0.0/win64.o/nt/bin",
        "D:/2026.1/2026.1/win64/tools/fpo_v7_1", environment["PATH"]))
    results = {}
    for group, suite in (("smoke", "smoke"), ("gate_t1", "b03_gate_t1")):
        original = ROOT / f"evidence/b03/batches/baseline/{group}/tv"
        work = DESTINATION / group
        shutil.copytree(original, work / "tv", dirs_exist_ok=True)
        checker = work / "wrapc_pc"
        checker.mkdir(parents=True, exist_ok=True)
        binary = checker / "cosim.pc.exe"
        shutil.copy2(EXECUTABLE, binary)
        log = ROOT / f"logs/b03/postcheck_audit_{group}.log"
        with log.open("wb") as output:
            process = subprocess.run([str(binary), "--suite", suite], cwd=checker, env=environment,
                                     stdout=output, stderr=subprocess.STDOUT, timeout=60)
        if process.returncode != 0:
            raise RuntimeError(f"Archived actual RTL replay failed: {group}: {process.returncode}")
        results[group] = {"exit_code": process.returncode, "log": str(log.relative_to(ROOT))}
    target = DESTINATION / "smoke/tv/rtldatafile/rtl.w4a8_linear_v1.autotvout_gmem_y.dat"
    original_hash = fingerprint(ROOT / "evidence/b03/batches/baseline/smoke/tv/rtldatafile" / target.name)
    payload = bytearray(target.read_bytes())
    # Binary TV begins with transaction/depth words, then big-endian FP32 Y[0]=890.
    if payload[8:12] != struct.pack(">f", 890.0):
        raise RuntimeError("Unexpected hand-sample RTL payload layout")
    payload[8:12] = struct.pack(">f", 0.0)
    target.write_bytes(payload)
    log = ROOT / "logs/b03/postcheck_audit_tampered.log"
    with log.open("wb") as output:
        process = subprocess.run([str(DESTINATION / "smoke/wrapc_pc/cosim.pc.exe"), "--suite", "smoke"],
                                 cwd=DESTINATION / "smoke/wrapc_pc", env=environment,
                                 stdout=output, stderr=subprocess.STDOUT, timeout=60)
    message = log.read_text(errors="replace")
    if process.returncode == 0 or "FAIL" not in message or "hand_sample" not in message:
        raise RuntimeError("Postchecker did not reject deliberately incorrect actual RTL Y")
    if fingerprint(ROOT / "evidence/b03/batches/baseline/smoke/tv/rtldatafile" / target.name) != original_hash:
        raise RuntimeError("Archived evidence was modified")
    report = {"status": "PASS", "postchecker_sha256": fingerprint(EXECUTABLE),
              "archived_actual_rtl_replays": results,
              "consumer_negative_probe": {"scratch_only": True, "changed": "hand Y[0]: 890 -> 0",
                  "expected": "nonzero / FP32 mismatch", "actual_exit_code": process.returncode,
                  "log": str(log.relative_to(ROOT))}, "archived_evidence_unchanged": True}
    (ROOT / "reports/b03/postcheck_consumer_proof.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PASS: archived RTL replays accepted; incorrect actual RTL Y rejected; originals unchanged")


if __name__ == "__main__":
    main()
