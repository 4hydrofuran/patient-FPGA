"""Derive this A10 increment from immutable captures; never contact the board."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def json_lines(text):
    rows = []
    for line in text.splitlines():
        if line.startswith("{"):
            rows.append(json.loads(line))
    return rows


def summarize(root):
    sources = []

    def load(name, require_exit=False):
        data = (root / name).read_bytes()
        obj = json.loads(data.decode("utf-8-sig"))
        sources.append({"path": name, "sha256": hashlib.sha256(data).hexdigest()})
        if require_exit and obj.get("exit_code") != 0:
            raise ValueError("Non-successful source: " + name)
        return obj

    resume = load("uart_resume_preflight_02.json", True)
    transfer = load("uart_linkage_transfer_01.json", True)
    linkage = load("uart_linkage_once_01.json", True)
    ip = load("uart_temporary_ip_add_01.json", True)
    board = load("uart_xrt_sections_01.json", True)
    package = load("xrt_package_sections_v1.json", True)
    inventory = load("ssh_platform_inventory_01.json")
    if inventory["boot_id"] not in resume["raw"] or inventory["boot_id"] not in linkage["command"]:
        raise ValueError("Boot identity mismatch")
    if "LINKAGE_ONLY_NO_DEVICE_OPEN\r\n" not in linkage["raw"]:
        raise ValueError("Missing linkage-only result")
    timing, = [r for r in json_lines(linkage["raw"]) if "linkage_exit" in r]
    if timing["linkage_exit"] != 0 or timing["elapsed_s"] >= 3:
        raise ValueError("Invalid linkage result")
    if not re.search(r"eth0\s+UP\s+192\.168\.2\.2/24\s*\r?\n", ip["raw"]):
        raise ValueError("Missing actual temporary address readback")
    if "DEFAULT_ROUTE_BEFORE\r\neth0" not in ip["raw"] or "DEFAULT_ROUTE_AFTER\r\nSSH_READONLY_STATUS" not in ip["raw"]:
        raise ValueError("Default route evidence changed; manual review required")
    if any(c["exit_code"] != 0 for c in inventory["commands"]):
        raise ValueError("Read-only inventory incomplete")
    by_name = lambda rows: {Path(r["path"]).name: r for r in rows}
    board_rows = by_name(json_lines(board["raw"]))
    pkg_rows = by_name(json_lines(package["stdout"]))
    if len(board_rows) != 2 or board_rows.keys() != pkg_rows.keys():
        raise ValueError("Missing XRT section rows")
    differences = {}
    for name, row in board_rows.items():
        bs = {s["name"]: s for s in row["sections"]}
        ps = {s["name"]: s for s in pkg_rows[name]["sections"]}
        if bs.keys() != ps.keys():
            raise ValueError("Section sets differ")
        differences[name] = {"board_sha256": row["sha256"], "package_sha256": pkg_rows[name]["sha256"],
                             "different_sections": [n for n in bs if bs[n] != ps[n]]}
    tests = {name: load(name, True)["exit_code"] for name in ["elf_section_tests_v4.json", "linkage_payload_tests_v2.json"]}
    return {
        "schema": "A10_LINKAGE_NETWORK_INCREMENT_V1", "status": "PARTIAL_NOT_A10_PASS",
        "boot_id": inventory["boot_id"], "sources": sources,
        "linkage_only": {"status": "PASS", **timing, "transfer_exit": transfer["exit_code"],
                         "fpga_device_opened": False},
        "temporary_network": {"address": "192.168.2.2/24", "interface": "eth0", "exit_code": ip["exit_code"],
                              "default_route": None, "persistent_config_changed": False,
                              "rollback_command_not_executed": "sudo ip -4 addr del 192.168.2.2/24 dev eth0"},
        "ssh_inventory": {"elapsed_s": inventory["elapsed_s"], "temperatures_c": [t / 1000 for t in inventory["temperatures_mC"]],
                          "overlays": inventory["overlays"]},
        "xrt_sections": differences, "xrt_rodata_difference_explained": False,
        "pc_test_receipts": tests,
        "BOARD_compute": "NOT_TESTED", "real_comparisons": 0, "BO_reachability": None,
        "PL_recovery": "NOT_TESTED", "pl_load_authorized": False,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = summarize(args.directory)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
