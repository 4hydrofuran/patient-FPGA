"""Copy small original HLS/XSIM reports into the Git-deliverable evidence tree."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "B01": (
        "build/b01_hls/hls/syn/report/csynth.rpt",
        "build/b01_hls/hls/sim/verilog/w4a8_linear_v1.performance.result.transaction.xml",
        "logs/b01/xsim_recovered.log",
        "logs/b01/rtl_postcheck.log",
    ),
    "B02_CACHE_X": (
        "build/b02_cache_x_hls/hls/syn/report/csynth.rpt",
        "build/b02_cache_x_hls/hls/sim/verilog/w4a8_linear_v1.performance.result.transaction.xml",
        "logs/b02/xsim_recovered.log",
        "logs/b02/rtl_postcheck.log",
    ),
    "B02_X128": (
        "build/b02_x128_hls/hls/syn/report/csynth.rpt",
        "build/b02_x128_hls/hls/sim/verilog/w4a8_linear_v1.performance.result.transaction.xml",
        "logs/b02/x128/cosim.log",
    ),
}


def main() -> None:
    dest = ROOT / "evidence/b02/ablation_raw"
    files = {}
    for variant, sources in SOURCES.items():
        for relative in sources:
            source = ROOT / relative
            target = dest / variant / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            files[str(target.relative_to(ROOT)).replace("\\", "/")] = {
                "source": relative,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "bytes": target.stat().st_size,
            }
    output = ROOT / "reports/b02/ablation_raw_manifest.json"
    output.write_text(json.dumps({"stage": "B02", "files": files}, indent=2) + "\n", encoding="utf-8")
    print(f"Copied {len(files)} raw reports/logs")


if __name__ == "__main__":
    main()
