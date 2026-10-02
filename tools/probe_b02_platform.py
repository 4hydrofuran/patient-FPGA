"""Read the installed KV260 platform metadata without modifying the platform."""

import hashlib
import json
import sys
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: probe_b02_platform.py <installed kv260_base.xpfm> <output.json>")
    xpfm = Path(sys.argv[1]).resolve(strict=True)
    xsa = (xpfm.parent / "hw" / "hw.xsa").resolve(strict=True)
    with zipfile.ZipFile(xsa) as archive:
        bd = json.loads(
            archive.read("prj/my_project.srcs/sources_1/bd/MPSoC_ext_platform/MPSoC_ext_platform.bd")
        )["design"]
    components = bd["components"]
    ps = components["ps_e"]
    clocks = components["clk_wiz_0"]
    full = components["smartconnect_axifull"]
    lpd = components["axi_smartconnect_lpd"]
    result = {
        "stage": "B02",
        "scope": "installed KV260 base platform metadata; no kernel link or board profile verification",
        "xpfm": str(xpfm),
        "xpfm_sha256": sha256(xpfm),
        "xsa": str(xsa),
        "xsa_sha256": sha256(xsa),
        "device": bd["design_info"]["device"],
        "default_clock_mhz": float(clocks["parameters"]["CLKOUT1_REQUESTED_OUT_FREQ"]["value"]),
        "default_clock_tag": clocks["pfm_attributes"]["CLOCK"],
        "ps_ddr_ports": {
            "HP3_FPD": {
                "enabled": "S_AXI_HP3_FPD" in ps["interface_ports"],
                "data_width_bits": int(ps["parameters"]["PSU__SAXIGP5__DATA_WIDTH"]["value"]),
                "platform_connectivity": full["pfm_attributes"]["AXI_PORT"],
            },
            "LPD": {
                "enabled": "S_AXI_LPD" in ps["interface_ports"],
                "data_width_bits": int(ps["parameters"]["PSU__SAXIGP6__DATA_WIDTH"]["value"]),
                "platform_connectivity": lpd["pfm_attributes"]["AXI_PORT"],
            },
        },
        "runtime_board_profile_verified": False,
        "physical_ddr_bandwidth_measured": False,
    }
    output = Path(sys.argv[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}; HP3/LPD=128 bit, default clock=150 MHz")


if __name__ == "__main__":
    main()
