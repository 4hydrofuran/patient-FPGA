"""Stream the audited read-only exporter over pinned SSH; retain failed output."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
from original_module_backup import verify_archive

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "platform/local/a10-boot-backup-20261020/modules-v1"

if __name__ == "__main__":
    known = ROOT / "platform/qwen35/a10/board_ssh_known_hosts"
    assert known.read_text().strip() == (
        "192.168.2.2 ssh-ed25519 "
        "AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe")
    code = Path(__file__).with_name("original_module_backup.py").read_bytes()
    OUT.mkdir(parents=True, exist_ok=False)
    args = ["C:/Windows/System32/OpenSSH/ssh.exe", "-T",
            "-o", "BindAddress=192.168.2.1",
            "-o", f"UserKnownHostsFile={known.as_posix()}",
            "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5",
            "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
            "-o", "NumberOfPasswordPrompts=1", "-o", "PubkeyAuthentication=no",
            "ubuntu@192.168.2.2",
            "nice -n 19 python3 - --stream-readonly"]
    report = dict(argv=args, exporter_sha256=hashlib.sha256(code).hexdigest(),
                  board_file_writes=False, status="NOT_VERIFIED")
    start = time.monotonic()
    try:
        with (OUT / "original-modules.tar").open("xb") as stream:
            # SSH uses its console for interactive auth, not script stdin or
            # archive stdout. No credential is handled or stored here.
            result = subprocess.run(args, input=code, stdout=stream, timeout=120)
        report["exit_code"] = result.returncode
        if result.returncode:
            raise RuntimeError("SSH export failed; partial archive retained")
        proof = verify_archive(OUT / "original-modules.tar")
        with (OUT / "original-backup-proof.json").open("x") as file:
            json.dump(proof, file, indent=2)
        report.update(status="VERIFIED_PC_BACKUP",
                      archive_sha256=proof["archive_sha256"],
                      archive_bytes=proof["archive_bytes"], entries=len(proof["rows"]),
                      tree_sha256=proof["tree_sha256"])
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        report["elapsed_s"] = time.monotonic() - start
        with (OUT / "download.json").open("x") as file:
            json.dump(report, file, indent=2)
    print(json.dumps(report))
    raise SystemExit(0 if report["status"] == "VERIFIED_PC_BACKUP" else 2)
