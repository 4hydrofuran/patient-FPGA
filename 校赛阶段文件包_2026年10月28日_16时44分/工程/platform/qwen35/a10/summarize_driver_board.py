"""Offline evidence summary; never opens a serial port or modifies board state."""
import argparse
import hashlib
import json
from pathlib import Path
import re

MODULE_SHA = "545df42c8b66396dd847ccd6a280f19d9a0051d36e2e75c1ec84437caca328a9"
SRCVERSION = "97E8D4CCD40C7980154D120"


def output_text(capture):
    """Exclude shell command echo: a typed command is not an observed result."""
    raw = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", capture["raw"]).replace("\r", "\n")
    begin = re.search(r"(?m)^(A10_[a-f0-9]+)_BEGIN$", raw)
    if not begin:
        raise ValueError("Missing executed BEGIN marker")
    end = re.search(r"(?m)^" + re.escape(begin[1]) + r"_END:(\d+)$", raw[begin.end():])
    if not end or int(end[1]) != capture["exit_code"]:
        raise ValueError("Missing/mismatched executed END marker")
    return raw[begin.end():begin.end() + end.start()]


def summarize(folder):
    sources = []

    def load(name, rc=None):
        path = folder / name
        data = path.read_bytes()
        value = json.loads(data.decode("utf-8-sig"))
        if value.get("closed") is not True:
            raise ValueError("Serial not confirmed closed: " + name)
        if rc is not None and value.get("exit_code") != rc:
            raise ValueError("Unexpected exit: " + name)
        sources.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                        "utc": value.get("utc"), "exit_code": value.get("exit_code"),
                        "status": value.get("status"), "elapsed_s": value.get("elapsed_s")})
        return value

    baseline = output_text(load("uart_driver_kernel_baseline_01.json", 0))
    transfer = load("uart_driver_serial_transfer_02.json", 0)
    if (transfer["status"] != "PASS_HASH_VERIFIED_NO_EXECUTION"
            or transfer["sha256"] != MODULE_SHA or transfer["bytes"] != 464752
            or transfer["chunks"] != 167 or len(transfer["acks"]) != 167
            or "A10DRV_DONE:" + MODULE_SHA not in transfer["raw"]):
        raise ValueError("Transfer evidence incomplete")
    loaded = output_text(load("uart_driver_load_01.json", 0))
    post = output_text(load("uart_driver_post_01.json", 0))
    unload = load("uart_driver_unload_01.json", 0)
    unloaded = output_text(unload)
    closed = load("uart_driver_closed_check_01.json", 0)
    after = output_text(closed)
    if not all(s in loaded for s in ["binding_candidates []", "2.18.0", SRCVERSION]):
        raise ValueError("Version/no-binding evidence missing")
    if not re.search(r"(?m)^zocl\s+294912\s+0\s*$", post):
        raise ValueError("Loaded module/refcount evidence missing")
    if ("test ! -d /sys/module/zocl" not in closed["command"]
            or "test ! -d /sys/bus/platform/drivers/zocl-drm" not in closed["command"]
            or "sudo -n /usr/sbin/rmmod zocl" not in unload["command"]
            or "binding_candidates []" not in unloaded):
        raise ValueError("Normal unload/absence evidence missing")
    if not all(re.search(r"(?m)^" + str(v) + r"$", text) for v, text in
               [(8704, baseline), (12800, loaded), (12800, unloaded), (12800, after)]):
        raise ValueError("Taint evidence mismatch")
    if MODULE_SHA not in after or "k26-starter-kits_image_1" not in after:
        raise ValueError("Closing hash/default-overlay observation missing")
    temps = json.loads(re.search(r"temperatures_mC (\[[0-9, ]+\])", after)[1])
    if not temps or not all(0 < t < 60000 for t in temps):
        raise ValueError("Closing temperature evidence invalid/hot")
    memory = {k: int(re.search(r"(?m)^" + k + r":\s+(\d+) kB", after)[1])
              for k in ["MemAvailable", "CmaFree"]}
    fw = output_text(load("uart_bootfw_readonly_01.json", 1))
    integrity = output_text(load("uart_kernel_integrity_01.json", 0))
    for name in ["uart_driver_privileged_preflight_01.json", "uart_driver_firmware_inventory_01.json",
                 "uart_unbound_preflight_01.json", "uart_driver_stage_01.json",
                 "uart_transfer_diagnostics_01.json", "uart_transfer_diagnostics_02.json",
                 "uart_driver_serial_transfer_01.json"]:
        load(name)
    return {
        "schema": "A10_DRIVER_BOARD_INCREMENT_V1", "domain": "BOARD",
        "status": "PASS_UNBOUND_DRIVER_LOAD_AND_NORMAL_UNLOAD_ONLY",
        "A10": "NOT_PASSED", "base_profile": "board_profile.json",
        "sources": sources,
        "module": {"sha256": MODULE_SHA, "bytes": 464752, "version": "2.18.0",
                   "srcversion": SRCVERSION, "system_install": False,
                   "board_path": "/home/ubuntu/a10-driver-check-20261018-v2/zocl.ko",
                   "loaded_then_unloaded": True, "bound_compute_device": False},
        "transfer": {"elapsed_s": transfer["elapsed_s"], "compressed_bytes": transfer["compressed_bytes"],
                     "chunks_acknowledged": len(transfer["acks"]), "receiver_sha256": transfer["receiver_sha256"]},
        "closing": {"utc": closed["utc"], "temperature_c": [t / 1000 for t in temps],
                    "memory_kib": memory, "kernel_taint": 12800, "serial_released": True,
                    "default_overlay_observed": "k26-starter-kits_image_1"},
        "preexisting_taint": 8704, "taint_added": 4096,
        "taint_unload_does_not_clear_history": True,
        "firmware": {"metadata_string": re.search(r"XilinxSom_QspiImage_\S+", fw)[0],
                     "active_firmware_revision": None, "image_revision_info": "Not defined",
                     "api_feature_warning_in_boot_log": "Expected firmware version is 2023.1" in baseline},
        "fru": {"carrier_product_read": "SCK-KV-G", "carrier_serial_read": "XFL1CYYPZ52Y",
                "checksum_error": "multirecord area checksum invalid" in fw,
                "fully_verified": False, "som_identity": None},
        "installed_vmlinuz_sha256": re.search(r"(?m)^([a-f0-9]{64})  /boot/vmlinuz", integrity)[1],
        "boot_fit_to_running_kernel_verified": False,
        "PL_load": "NOT_PERFORMED", "BO": "NOT_TESTED", "vadd": "NOT_TESTED",
        "vadd_board_comparisons": 0, "DMA_timeout_recovery": "NOT_TESTED",
        "arm_userspace_smoke": "NOT_TESTED", "A53_3200MiB_envelope": "NOT_VALIDATED",
        "measurement_limits": ["Elapsed values are whole command/transfer wall times, not driver or compute benchmarks.",
                               "Temperatures are discrete samples, not continuous peak measurements.",
                               "CMA is not additive with PSS/BO/MemTotal.",
                               "FRU/boot warnings do not by themselves establish physical board damage."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.folder)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "A10": result["A10"], "sources": len(result["sources"])}))
