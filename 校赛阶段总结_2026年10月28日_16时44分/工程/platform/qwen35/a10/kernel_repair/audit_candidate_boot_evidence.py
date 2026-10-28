"""PC-only audit of retained stage/boot/reconnect evidence; no board commands."""
import base64
import hashlib
import json
from pathlib import Path
import re
import zlib

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / "evidence/board_platform/A10_20261018_intake"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

def clean(text):
    return ANSI.sub("", text).replace("\r", "")

def decode_log(text):
    rows = []
    for line in clean(text).splitlines():
        if line.startswith('{"bytes":'):
            rows.append(json.loads(line))
    if len(rows) != 1:
        raise ValueError("Missing or ambiguous compressed log")
    row = rows[0]
    if not 0 < row["bytes"] <= 1048576:
        raise ValueError("Log budget")
    d = zlib.decompressobj()
    raw = d.decompress(base64.b64decode(row["zlib_base64"], validate=True), 1048577)
    if not d.eof or d.unconsumed_tail or d.unused_data or len(raw) != row["bytes"]:
        raise ValueError("Truncated/trailing/oversize log")
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("Log hash mismatch")
    return raw

def read(name):
    return json.loads((E / name).read_text(encoding="utf-8-sig"))

def post(record):
    return clean(next(r["text"] for r in record["events"] if r["kind"] == "postcheck_result"))

def observations(text):
    return dict(
        kernel=re.search(r"(?m)^Linux kria (\S+)", text)[1],
        boot_id=re.search(r"(?m)^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$", text)[0],
        temperatures_mC=json.loads(re.search(r"temperatures_mC (\[[\d, ]+\])", text)[1]),
        memory_KiB={key:int(value) for key,value in re.findall(
            r"(?m)^(MemTotal|MemAvailable|CmaTotal|CmaFree):\s*(\d+) kB",text)})

def audit():
    before = read("candidate_login_readback_01.json")
    resumed = read("power_resume_readback_20261020_02.json")
    historical = read("previous_candidate_kernel_log_01.json")
    if historical["exit_code"] != 0 or resumed["postcheck_exit"] != 0:
        raise ValueError("Readback collection incomplete")
    previous_log = decode_log(historical["raw"])
    current_log = decode_log(post(resumed))
    candidate = observations(post(before))
    current = observations(post(resumed))
    if candidate["kernel"] != "6.8.12-a10irq1" or current["kernel"] != "6.8.0-1015-xilinx":
        raise ValueError("Unexpected kernels")
    if b"Linux version 6.8.12-a10irq1 " not in previous_log:
        raise ValueError("Archived log not candidate")
    stage = json.loads(read("candidate_stage_independent_readback_01.json")["stdout"])
    rows = [json.loads(s) for s in stage["raw_stage_jsonl"].splitlines()]
    if rows[-1]["event"] != "STAGED_ONLY_NOT_BOOTED" or stage["active_stage_pids"]:
        raise ValueError("Stage incomplete")
    health = [r for r in rows if r["event"] == "HEALTH"]
    source_names = [
        "uart_candidate_temp_network_01.json", "uart_candidate_network_readback_01.json",
        "uart_candidate_stage_01.json", "candidate_stage_independent_readback_01.json",
        "candidate_boot_once_01.json", "candidate_boot_continue_01.json",
        "candidate_login_readback_01.json", "power_resume_readback_20261020_01.json",
        "power_resume_readback_20261020_02.json", "previous_candidate_kernel_log_01.json"]
    for name, data in (("candidate_kernel_archived.txt",previous_log),
                       ("power_resume_kernel.txt",current_log)):
        with (E / name).open("xb") as file:
            file.write(data)
    report = dict(
        schema="A10_CANDIDATE_BOOT_AND_ORIGINAL_RETURN_V1",
        status="CANDIDATE_LINUX_BOOT_VERIFIED_ORIGINAL_RETURN_VERIFIED_A10_NOT_PASSED",
        candidate_boot=candidate, current_readback=current,
        candidate_first_postcheck_exit=before["postcheck_exit"],
        candidate_first_log_timeout_preserved=True,
        candidate_archived_log_exit=historical["exit_code"],
        current_readback_exit=resumed["postcheck_exit"],
        stage_seconds=rows[-1]["monotonic_s"]-rows[0]["monotonic_s"],
        stage_health_samples=len(health),
        stage_max_temperature_mC=max(t for r in health for t in r["temperatures_mC"]),
        stage_min_MemAvailable_KiB=min(r["MemAvailable_KiB"] for r in health),
        stage_module_readback=next(r for r in rows if r["event"]=="MODULE_READBACK"),
        candidate_boot_commands_sent=read("candidate_boot_continue_01.json")["boot_commands_sent"],
        agent_normal_reboots=read("candidate_boot_once_01.json")["reboot_commands_sent"],
        current_original_boot_return_cause="USER_REPORTED_POWER_CYCLE_NOT_AGENT_FAULT_INJECTION",
        original_boot_hashes=stage["boot_hashes"],
        compute_runs=0, compute_BO_allocations=0, numerical_regression="CANCELLED_BY_USER",
        IRQ_fix_board_verification="NOT_TESTED_NO_TEST_PL_CYCLE",
        source_sha256={n:hashlib.sha256((E/n).read_bytes()).hexdigest() for n in source_names},
        logs={n:dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
              for n,b in (("candidate_kernel_archived.txt",previous_log),("power_resume_kernel.txt",current_log))})
    with (E / "candidate_boot_and_return_audit.json").open("x") as file:
        json.dump(report,file,indent=2)
    return report

if __name__=="__main__":
    print(json.dumps(audit(),indent=2))
