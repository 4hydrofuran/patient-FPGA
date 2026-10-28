"""Authorized candidate upload only: new user directory, no system installation."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from stage_candidate_board import PINNED, SOURCE, BOOT, MACHINE_SHA
REMOTE = SOURCE.as_posix()

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "platform/local/a10-candidate-transfer-20261020-v1"
WSL = Path("//wsl.localhost/KV260-A-2204/home/member-a/a10-kernel-full-20261019-v1/boot-candidate-v2")

def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

if __name__ == "__main__":
    known = ROOT / "platform/qwen35/a10/board_ssh_known_hosts"
    assert known.read_text().strip() == (
        "192.168.2.2 ssh-ed25519 "
        "AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe")
    proof = ROOT / "platform/local/a10-boot-backup-20261020/modules-v1/original-backup-proof.json"
    p = json.loads(proof.read_text())
    assert p["status"] == "VERIFIED_PC_BACKUP" and p["identity"]["boot_id"] == BOOT
    OUT.mkdir(parents=True, exist_ok=False)
    sources = [WSL / name for name in PINNED] + [
        Path(__file__).with_name("stage_candidate_board.py"),
        Path(__file__).with_name("original_module_backup.py"), proof]
    for source in sources:
        shutil.copyfile(source, OUT / source.name)
    for name, (size, digest) in PINNED.items():
        assert (OUT / name).stat().st_size == size and sha(OUT / name) == digest
    hashes = {p.name: sha(OUT / p.name) for p in sources}
    options = ["-o", "BindAddress=192.168.2.1",
               "-o", f"UserKnownHostsFile={known.as_posix()}",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5",
               "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
               "-o", "NumberOfPasswordPrompts=1", "-o", "PubkeyAuthentication=no"]
    guard = (
        f"set -e; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {BOOT}; "
        f"test \"$(sha256sum /etc/machine-id | cut -d ' ' -f1)\" = {MACHINE_SHA}; "
        "test ! -d /sys/module/zocl; test \"$(uname -r)\" = 6.8.0-1015-xilinx; "
        "python3 -c \"from pathlib import Path; t=[int(p.read_text()) for p in "
        "Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]; print(t); "
        "assert t and all(0<x<55000 for x in t)\"; "
        f"umask 077; mkdir {REMOTE}")
    report = dict(status="NOT_UPLOADED", hashes=hashes, commands=[], system_install=False)
    start = time.monotonic()
    try:
        commands = [
            ["C:/Windows/System32/OpenSSH/ssh.exe", "-T", *options, "ubuntu@192.168.2.2", guard],
            ["C:/Windows/System32/OpenSSH/scp.exe", "-l", "65536", *options,
             *[str(OUT / p.name) for p in sources], f"ubuntu@192.168.2.2:{REMOTE}/"],
            ["C:/Windows/System32/OpenSSH/ssh.exe", "-T", *options, "ubuntu@192.168.2.2",
             f"cd {REMOTE} && " + " && ".join(
                 f"test \"$(sha256sum {shlex.quote(name)} | cut -d ' ' -f1)\" = {value}"
                 for name, value in hashes.items()) + " && printf 'ALL_UPLOAD_HASHES_MATCH\\n'"]
        ]
        for cmd in commands:
            result = subprocess.run(cmd)
            report["commands"].append(dict(argv=cmd, exit_code=result.returncode))
            if result.returncode:
                raise RuntimeError("Upload step failed; no retry or deletion")
        report["status"] = "UPLOADED_HASH_VERIFIED_NOT_INSTALLED"
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        report["elapsed_s"] = time.monotonic() - start
        with (OUT / "upload.json").open("x") as f:
            json.dump(report, f, indent=2)
    print(json.dumps(report))
    raise SystemExit(0 if report["status"] == "UPLOADED_HASH_VERIFIED_NOT_INSTALLED" else 2)
