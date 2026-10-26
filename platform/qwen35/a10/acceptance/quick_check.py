#!/usr/bin/env python3
"""Short KV260 intake: no flash, register writes, XRT load, or automatic reboot.

Only --cpu runs a bounded single-thread ordinary userspace computation.
This is not A10 full acceptance or permission to deploy the project's xclbin.
"""
import argparse
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
EXPECTED_KERNEL = "6.18.10-xilinx-g4f7afe14f724"
CAP = 262144


def read(path):
    try:
        with open(path, "rb") as stream:
            data = stream.read(CAP + 1)
        return {"status": "OK", "text": data[:CAP].replace(b"\0", b"\n").decode("utf-8", "replace"),
                "truncated": len(data) > CAP, "sha256_of_read_bytes": hashlib.sha256(data[:CAP]).hexdigest()}
    except OSError as exc:
        return {"status": "NOT_READ", "reason": str(exc)}


def temperatures(root=Path("/sys/class/thermal"), hwmon_root=Path("/sys/class/hwmon")):
    """Keep failed readings visible. hwmon is the observed KV260 sensor path.

    Duplicate thermal/hwmon readings are observations, not additive quantities.
    Any missing/invalid enumerated sensor blocks a subsequent CPU test.
    """
    values = []

    def sample(path, source, zone, label_path):
        item = {"source": source, "path": str(path), "zone": zone,
                "type": None, "celsius": None, "status": "NOT_READ"}
        try:
            with path.open() as stream:
                raw = stream.read(129)
            if len(raw) > 128:
                raise ValueError("Temperature reading exceeds 128 byte cap")
            value = int(raw.strip()) / 1000.0
            if not math.isfinite(value) or not 0 < value <= 150:
                raise ValueError("Temperature outside conservative plausible range (0,150] C")
            item.update(celsius=value, status="OK")
        except (OSError, ValueError, OverflowError) as exc:
            item["reason"] = str(exc)
        try:
            with label_path.open() as stream:
                item["type"] = stream.read(128).strip()
        except OSError:
            pass  # A human-readable label is optional; the reading is not.
        values.append(item)

    def bounded(paths):
        paths = sorted(paths)
        if len(paths) > 16:
            values.append({"source": "enumeration", "celsius": None,
                           "status": "NOT_READ", "reason": "Sensor enumeration exceeds cap"})
        return paths[:16]

    for zone in bounded(root.glob("thermal_zone*")):
        sample(zone / "temp", "thermal", zone.name, zone / "type")
    for monitor in bounded(hwmon_root.glob("hwmon*")):
        for sensor in bounded(monitor.glob("temp*_input")):
            sample(sensor, "hwmon", monitor.name, monitor / "name")
    return values


def temperature_gate(temps):
    if not temps:
        return "Temperature unavailable; no further test permitted"
    for item in temps:
        value = item.get("celsius")
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0 < value <= 150
                or item.get("status", "OK") != "OK"):
            return "Temperature invalid/unreadable; no further test permitted"
    if max(item["celsius"] for item in temps) >= 60:
        return "At or above conservative 60 C stop threshold (not device rating)"
    return None


def cpu_gate(machine, meminfo, temps, confirmed):
    if machine != "aarch64" or not confirmed:
        return "KV260 identity confirmation / aarch64 required"
    match = re.search(r"^MemAvailable:\s+(\d+)\s+kB", meminfo, re.M)
    if not match or int(match[1]) < 262144:
        return "MemAvailable unknown or below conservative 256 MiB floor"
    return temperature_gate(temps)


def command(argv, output, name, seconds=3):
    """Files retain errors/timeouts. No shell, no retry loop, no device commands."""
    started = time.monotonic()
    with (output / (name + ".stdout")).open("xb") as out, (output / (name + ".stderr")).open("xb") as err:
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err, timeout=seconds, check=False)
            code, state = result.returncode, "PASS" if result.returncode == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            code, state = None, "TIMEOUT"
        except OSError as exc:
            code, state = None, "NOT_TESTED"
            err.write(str(exc).encode())
    return {"argv": argv, "status": state, "exit_code": code, "elapsed_s": time.monotonic() - started}


def verify_helper():
    binary = HERE / "cpu_smoke_a53"
    manifest = json.loads((HERE / "SHA256.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    if digest != manifest["cpu_smoke_a53"]:
        raise ValueError("CPU binary hash mismatch")
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="NEW report directory; never overwrite")
    parser.add_argument("--board-label", required=True, help="Actual new board label/serial recorded by user")
    parser.add_argument("--confirm-kv260", action="store_true", help="User has checked actual board is KV260, stable supply/fan and no other tests")
    parser.add_argument("--cpu", action="store_true", help="Opt in: one 4 MiB pass, one thread, 3 second hard child timeout")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "aarch64":
        parser.error("REFUSED: board entry requires Linux aarch64; PC unit tests are separate")
    if not args.board_label.strip() or not args.confirm_kv260:
        parser.error("Confirm real KV260 identity and power/cooling first")
    output = Path(args.output)
    output.mkdir(parents=False, exist_ok=False)
    started = time.monotonic()
    report = {"schema": "KV260_SHORT_INTAKE_V1", "domain": "BOARD", "scope": "BASIC_INTAKE_NOT_FULL_PROJECT",
              "board_label_user_supplied": args.board_label, "identity_source": "USER_CONFIRMATION_PLUS_RAW_DT",
              "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "machine": platform.machine(), "kernel": platform.release(), "files": {},
              "cpu": {"status": "NOT_TESTED", "reason": "Not requested"},
              "FPGA": "NOT_TESTED", "model_voice": "NOT_TESTED", "A10_full": "NOT_PASSED",
              "bo_budget_bytes": None, "deployment": "PENDING_PLATFORM_REVIEW"}
    files = ["/etc/os-release", "/proc/meminfo", "/proc/cpuinfo", "/proc/cmdline", "/proc/modules",
             "/proc/device-tree/model", "/proc/device-tree/compatible", "/proc/device-tree/serial-number",
             "/sys/module/zocl/version", "/sys/module/zocl/srcversion", "/sys/module/zocl/taint",
             "/opt/xilinx/xrt/version.json"]
    for filename in files:
        report["files"][filename] = read(filename)
    report["device_nodes"] = sorted(str(p) for p in Path("/dev/dri").glob("*")) if Path("/dev/dri").exists() else []
    report["temperatures_before"] = temperatures()
    report["kernel_matches_locked_candidate"] = platform.release() == EXPECTED_KERNEL
    report["commands"] = [command(["ip", "-br", "address"], output, "network"),
                           command(["df", "-h", "/"], output, "root_space"),
                           command(["dmesg", "--color=never"], output, "kernel_log")]
    # Small bounded raw DT snapshot; do not edit the tree or guess CMA/PL mappings.
    fdt = Path("/sys/firmware/fdt")
    try:
        with fdt.open("rb") as stream:
            data = stream.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("FDT exceeds intake cap")
        (output / "running.dtb").write_bytes(data)
        report["running_dtb_sha256"] = hashlib.sha256(data).hexdigest()
    except (OSError, ValueError) as exc:
        report["running_dtb"] = {"status": "NOT_READ", "reason": str(exc)}
    if args.cpu:
        reason = cpu_gate(platform.machine(), report["files"]["/proc/meminfo"].get("text", ""),
                          report["temperatures_before"], args.confirm_kv260)
        if reason:
            report["cpu"] = {"status": "NOT_TESTED", "reason": reason}
        else:
            try:
                helper = verify_helper()
                helper.chmod(0o700)
                report["cpu"] = command([str(helper)], output, "cpu", 3)
            except (OSError, ValueError, KeyError) as exc:
                report["cpu"] = {"status": "FAIL", "reason": str(exc)}
    report["temperatures_after"] = temperatures()
    report["elapsed_s"] = time.monotonic() - started
    report["result"] = "COLLECTED_REVIEW_REQUIRED"
    if report["cpu"]["status"] in ("FAIL", "TIMEOUT"):
        report["result"] = "STOP_CPU_FAILURE_NO_RETRY"
    temperature_reason = temperature_gate(report["temperatures_after"])
    if temperature_reason:
        report["result"] = "STOP_TEMPERATURE_NO_FURTHER_TESTS"
        report["temperature_stop_reason"] = temperature_reason
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "cpu": report["cpu"]["status"], "report": str(output / "report.json"),
                      "FPGA": "NOT_TESTED", "model_voice": "NOT_TESTED"}, ensure_ascii=False))
    return 0 if report["result"] == "COLLECTED_REVIEW_REQUIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
