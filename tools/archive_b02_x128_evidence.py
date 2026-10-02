"""Preserve the native X128 Cosim vectors, RTL outputs, performance, and waveform."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "build/b02_x128_hls/hls/sim"
DEST = ROOT / "evidence/b02/x128_rtl_recovered"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    receipt = ROOT / "reports/b02/x128/cosim.receipt.json"
    recorded = json.loads(receipt.read_text(encoding="utf-8-sig"))
    if recorded["exit_code"] != 0:
        raise RuntimeError("Native Vitis Cosim did not exit successfully")
    log = ROOT / "logs/b02/x128/cosim.log"
    text = log.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"RTL Simulation\s*:\s*25\s*/\s*25", text):
        raise RuntimeError("XSIM did not complete all 25 transactions")
    if "B02 PASS suite=cosim" not in text:
        raise RuntimeError("Vitis C postchecker did not report PASS")

    files = []
    for directory in (SIM / "tv/cdatafile", SIM / "tv/rtldatafile"):
        files.extend(sorted(path for path in directory.iterdir() if path.is_file()))
    files.extend(
        SIM / "verilog" / name
        for name in (
            "run_xsim.bat",
            "w4a8_linear_v1.tcl",
            "w4a8_linear_v1.wdb",
            "w4a8_linear_v1.performance.result.transaction.xml",
            "w4a8_linear_v1.result.lat.rb",
        )
    )
    if any(not path.is_file() for path in files):
        raise RuntimeError("One or more Cosim evidence files are missing")

    hashes = {}
    for source in files:
        relative = source.relative_to(SIM)
        target = DEST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            try:
                os.link(source, target)
            except OSError:
                shutil.copy2(source, target)
        hashes[str(relative).replace("\\", "/")] = digest(target)

    source_paths = [
        "src/w4a8_linear_v1.cpp",
        "src/w4a8_linear_v1.hpp",
        "tb/tb_w4a8_linear_v1.cpp",
        "tb/golden_w4a8.hpp",
        "hls_b02_x128.cfg",
    ]
    report = {
        "stage": "B02",
        "variant": "X128",
        "status": "PASS_NATIVE_COSIM",
        "vitis_cosim_exit_code": 0,
        "rtl_transactions": 25,
        "scope": "synthetic boundary/error/repeat cases and two target T1 shapes",
        "input_sha256": {name: digest(ROOT / name) for name in source_paths},
        "evidence_files_sha256": hashes,
        "waveform_bytes": (DEST / "verilog/w4a8_linear_v1.wdb").stat().st_size,
    }
    output = ROOT / "reports/b02/x128/rtl_evidence.receipt.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Archived {len(files)} files to {DEST}")


if __name__ == "__main__":
    main()
