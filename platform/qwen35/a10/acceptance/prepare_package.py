"""Build/test/package locally. Never connects to a board. New destinations only."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence/board_platform/newboard_short_20261016_v1"
RELEASE = ROOT / "release/kv260_user_acceptance_20261016_v1"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def record(name, argv, timeout=90):
    start = time.monotonic()
    completed = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=timeout)
    (EVIDENCE / (name + ".stdout")).write_bytes(completed.stdout)
    (EVIDENCE / (name + ".stderr")).write_bytes(completed.stderr)
    result = {"argv": argv, "exit_code": completed.returncode, "elapsed_s": time.monotonic() - start}
    (EVIDENCE / (name + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if completed.returncode:
        raise RuntimeError("Failed: " + name + "; logs retained")
    return result


def main():
    if RELEASE.exists():
        raise SystemExit("Release exists; refuse overwrite")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    records = []
    for name, script in [("old-contract", "scripts/release/check_contracts.py"), ("qwen-contract", "scripts/release/qwen35_config.py")]:
        records.append(record(name, [sys.executable, "-X", "utf8", script]))
    records.append(record("unit-tests", [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", str(SOURCE), "-p", "test_quick_check.py", "-v"]))
    records.append(record("powershell-syntax", ["powershell", "-NoProfile", "-Command",
        "$tokens=$null; $parseErrors=$null; [System.Management.Automation.Language.Parser]::ParseFile('C:/Patientqwen/platform/qwen35/a10/acceptance/run_check.ps1',[ref]$tokens,[ref]$parseErrors) | Out-Null; if ($parseErrors.Count) { $parseErrors | Format-List; exit 1 }; 'PASS_POWERSHELL_PARSE_ONLY_NO_BOARD_CONNECTION'"]))
    records.append(record("build-dynamic-v2", ["wsl", "-d", "KV260-A-2204", "--", "bash",
        "/mnt/c/Patientqwen/platform/qwen35/a10/acceptance/build.sh",
        "/mnt/c/Patientqwen/evidence/board_platform/newboard_short_20261016_v1/build-dynamic-v2"]))
    RELEASE.mkdir(parents=True)
    payload = RELEASE / "user_check"
    payload.mkdir()
    names = ["quick_check.py", "cpu_smoke.c", "run_check.ps1", "用户验收说明.md", "给刷机人员.md"]
    for name in names:
        shutil.copy2(SOURCE / name, payload / name)
    shutil.copy2(EVIDENCE / "build-dynamic-v2/cpu_smoke_a53", payload / "cpu_smoke_a53")
    state = {"date": "2026-10-16", "PC_unit": "PASS_11", "PC_native_cpu": "PASS_SINGLE_4MIB_PASS_AND_DOT16",
             "PowerShell": "PARSE_PASS_REMOTE_WORKFLOW_NOT_TESTED", "ARM64_cross_build": "PASS_SDK_2026_1_CORTEX_A53_DYNAMIC",
             "BOARD": "NOT_TESTED", "FPGA": "NOT_TESTED", "model_voice_on_new_board": "NOT_TESTED",
             "A10": "NOT_PASSED", "initial_failure": "SDK static libc unavailable; first build exit1 retained. Explicit dynamic rebuild, no tool reinstall.",
             "remaining": ["Actual new board identity, SSH and running DT/XRT", "PL timeout lifecycle/platform matching", "Short full-application target test not delivered"]}
    (payload / "BUILD_STATUS.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    hashes = {p.name: digest(p) for p in sorted(payload.iterdir()) if p.is_file()}
    (payload / "SHA256.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")
    archive = RELEASE / "KV260_用户短时基础验收.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(payload.iterdir()):
            z.write(p, "user_check/" + p.name)
    # Separate technician folder: actual image files, not inaccessible local links.
    flash = RELEASE / "给刷机人员"
    flash.mkdir()
    shutil.copy2(SOURCE / "给刷机人员.md", flash / "给刷机人员.md")
    expected = {
        "edf-platform-disk-image-kria-amd-cortexa53-mali-common.rootfs-20260609231841.wic.xz": "b6b3cad154dc7bee1de51bfe51a17848c18efbeee9766ee55e850b2a6950aa9f",
        "BOOT-k26-smk-kv-sdt-multidomain-20260609231841.bin": "d08a66ba5c04c713ce663ecc74ffb4d34bc0f7e4885c6d0875c7961ce6e8e678"}
    for name, wanted in expected.items():
        if digest(ROOT / name) != wanted:
            raise RuntimeError("Original flash input hash mismatch: " + name)
        shutil.copy2(ROOT / name, flash / name)
        if digest(flash / name) != wanted:
            raise RuntimeError("Copied flash input hash mismatch: " + name)
    (flash / "SHA256.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    receipt = {"commands": records, "domains": state, "program_zip": str(archive), "program_zip_sha256": digest(archive),
               "program_zip_bytes": archive.stat().st_size, "technician_files": expected}
    (EVIDENCE / "RESULT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
