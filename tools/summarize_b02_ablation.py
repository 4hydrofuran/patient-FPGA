"""Extract comparable B02 synthesis and RTL measurements from local tool output."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {
    "B01": "b01_hls",
    "B02_CACHE_X": "b02_cache_x_hls",
    "B02_X128": "b02_x128_hls",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthesis(project: str) -> dict[str, object]:
    path = ROOT / "build" / project / "hls/syn/report/csynth.rpt"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    top = next(line for line in lines if line.startswith("|+ w4a8_linear_v1 "))
    fields = [part.strip() for part in top.split("|")]
    interface = next(line for line in lines if line.startswith("| m_axi_gmem_x "))
    interface_fields = [part.strip() for part in interface.split("|")]
    return {
        "report": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256(path),
        "clock_slack_ns_hls_estimate": float(fields[10]),
        "bram18k_hls_estimate": int(fields[11].split()[0]),
        "dsp_hls_estimate": int(fields[12].split()[0]),
        "ff_hls_estimate": int(fields[13].split()[0]),
        "lut_hls_estimate": int(fields[14].split()[0]),
        "gmem_x_width": interface_fields[3],
        "gmem_x_interface_bram_estimate": int(
            re.search(r"BRAM=(\d+)", interface).group(1)
        ),
    }


def rtl(project: str) -> dict[str, object]:
    path = ROOT / "build" / project / "hls/sim/verilog/w4a8_linear_v1.performance.result.transaction.xml"
    text = path.read_text(encoding="utf-8", errors="replace")
    transactions = {
        int(index): int(latency)
        for index, latency in re.findall(r"transaction\s+(\d+):\s+(\d+)", text)
    }
    if set(transactions) != set(range(25)):
        raise ValueError(f"incomplete 25-transaction RTL run: {path}")
    return {
        "performance_file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256(path),
        "transactions": len(transactions),
        "gate_up_t1_cycles": transactions[23],
        "down_t1_cycles": transactions[24],
    }


def main() -> None:
    measurements = {
        name: {"synthesis": synthesis(project), "rtl_xsim": rtl(project)}
        for name, project in VARIANTS.items()
    }
    baseline = measurements["B01"]["rtl_xsim"]
    for name in ("B02_CACHE_X", "B02_X128"):
        current = measurements[name]["rtl_xsim"]
        current["gate_up_vs_b01_cycles"] = current["gate_up_t1_cycles"] - baseline["gate_up_t1_cycles"]
        current["down_vs_b01_cycles"] = current["down_t1_cycles"] - baseline["down_t1_cycles"]
    output = {
        "stage": "B02",
        "tool": "Vitis HLS 2026.1 / XSIM",
        "clock_target_ns": 6.667,
        "clock_uncertainty_ns": 1.8,
        "rtl_scope": "25 synthetic transactions; target gate/up and down at T=1",
        "measurements": measurements,
        "limits": [
            "HLS resources and slack are estimates, not implemented timing.",
            "XSIM cycles exclude physical DDR contention and board software overhead.",
            "No T8 new-shape RTL or board results are claimed.",
        ],
    }
    path = ROOT / "reports/b02/ablation.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
