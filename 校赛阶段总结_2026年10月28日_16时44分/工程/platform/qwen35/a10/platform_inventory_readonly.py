"""A10: bounded read-only inventory, no accelerator opens or management calls."""
import json
import subprocess
import time
from pathlib import Path

BOOT = "d07af077-84c9-4910-8529-95757a09106d"


def read(path, limit=65536):
    p = Path(path)
    if not p.is_file():
        return None
    with p.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Read cap exceeded: " + path)
    return data.decode("utf-8", errors="replace")


def inventory():
    start = time.monotonic()
    boot = read("/proc/sys/kernel/random/boot_id").strip()
    if boot != BOOT:
        raise RuntimeError("Boot identity changed; no further inventory")
    temps = [int(read(str(p))) for p in Path("/sys/class/hwmon").glob("hwmon*/temp*_input")]
    if not temps or not all(0 < x < 60000 for x in temps):
        raise RuntimeError("Temperature gate")
    result = {"boot_id": boot, "temperatures_mC": temps, "commands": []}
    commands = [
        ["dpkg-query", "-L", "dfx-mgr", "libdfx-mgr2", "libdfx1.0", "xlnx-default-bitstreams"],
        ["systemctl", "show", "dfx-mgr", "--property=ActiveState,SubState,FragmentPath,ExecStart"],
    ]
    for cmd in commands:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if len(p.stdout) + len(p.stderr) > 65536:
            raise RuntimeError("Command output cap exceeded")
        result["commands"].append({"argv": cmd, "exit_code": p.returncode,
                                   "stdout": p.stdout, "stderr": p.stderr})
    result["files"] = {p: read(p) for p in [
        "/usr/bin/xmutil", "/etc/dfx-mgrd/daemon.conf", "/etc/dfx-mgr/daemon.conf",
        "/sys/class/fpga_manager/fpga0/state", "/proc/sys/kernel/tainted",
        "/proc/meminfo",
    ]}
    result["overlays"] = {}
    root = Path("/sys/kernel/config/device-tree/overlays")
    for p in list(root.iterdir())[:16] if root.exists() else []:
        result["overlays"][p.name] = {n: read(str(p / n), 4096) for n in ["path", "status"]}
    root = Path("/lib/firmware/xilinx")
    result["firmware_entries"] = []
    if root.is_dir():
        for p in list(root.glob("*/*"))[:128]:
            if p.is_file():
                item = {"path": str(p), "bytes": p.stat().st_size}
                if p.suffix == ".json":
                    item["text"] = read(str(p), 8192)
                result["firmware_entries"].append(item)
    result["elapsed_s"] = time.monotonic() - start
    return result


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=True))
