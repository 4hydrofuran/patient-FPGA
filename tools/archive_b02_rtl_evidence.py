"""Archive successful B02 RTL outputs, generated vectors, and the waveform."""

import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "build/b02_cache_x_hls/hls/sim"
DEST = ROOT / "evidence/b02/rtl_recovered"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    xsim_log = ROOT / "logs/b02/xsim_recovered.log"
    postcheck_log = ROOT / "logs/b02/rtl_postcheck.log"
    xsim_text = xsim_log.read_text(encoding="utf-8", errors="replace")
    postcheck_text = postcheck_log.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"RTL Simulation\s*:\s*25\s*/\s*25", xsim_text):
        raise RuntimeError("XSIM did not complete 25/25 transactions")
    if "B02 PASS suite=cosim" not in postcheck_text:
        raise RuntimeError("B02 C postchecker did not report PASS")
    for name in ("xsim_recovered", "rtl_postcheck", "xsim_relink"):
        receipt = ROOT / f"reports/b02/{name}.receipt.json"
        data = json.loads(receipt.read_text(encoding="utf-8-sig"))
        if data["exit_code"] != 0:
            raise RuntimeError(f"{name} exit code was not zero")

    files = []
    for directory in (SIM / "tv/cdatafile", SIM / "tv/rtldatafile"):
        files.extend(sorted(path for path in directory.iterdir() if path.is_file()))
    files.extend(
        SIM / "verilog" / name
        for name in (
            "run_xsim.bat",
            "run_b02_xelab.bat",
            "run_recovered_xsim.bat",
            "w4a8_linear_v1.tcl",
            "w4a8_linear_v1.wdb",
            "w4a8_linear_v1.performance.result.transaction.xml",
            "w4a8_linear_v1.result.lat.rb",
        )
    )
    files.extend(
        SIM / "wrapc_pc" / name
        for name in ("apatb_w4a8_linear_v1.cpp", "apatb_w4a8_linear_v1.h")
    )
    if any(not path.is_file() for path in files):
        raise RuntimeError("One or more RTL evidence files are missing")

    hashes = {}
    for source in files:
        relative = source.relative_to(SIM)
        target = DEST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[str(relative).replace("\\", "/")] = digest(target)

    source_paths = [
        "src/w4a8_linear_v1.cpp",
        "src/w4a8_linear_v1.hpp",
        "tb/tb_w4a8_linear_v1.cpp",
        "tb/golden_w4a8.hpp",
        "hls_b02_cache_x.cfg",
    ]
    report = {
        "stage": "B02",
        "status": "PASS_RECOVERED",
        "standard_vitis_cosim_exit_code": 1,
        "recovered_xsim_exit_code": 0,
        "postcheck_exit_code": 0,
        "rtl_transactions": 25,
        "scope": "synthetic boundary/error/repeat cases and two new target shapes T1",
        "input_sha256": {name: digest(ROOT / name) for name in source_paths},
        "snapshot_sha256": digest(SIM / "verilog/xsim.dir/w4a8_linear_v1/xsimk.exe"),
        "postchecker_sha256": digest(SIM / "wrapc_pc/cosim.pc.exe"),
        "evidence_files_sha256": hashes,
        "waveform_bytes": (DEST / "verilog/w4a8_linear_v1.wdb").stat().st_size,
    }
    output = ROOT / "reports/b02/rtl_recovered_summary.receipt.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Archived {len(files)} files and waveform to {DEST}")


if __name__ == "__main__":
    main()
