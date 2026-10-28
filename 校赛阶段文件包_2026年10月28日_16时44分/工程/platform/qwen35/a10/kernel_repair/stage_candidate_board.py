"""Explicit, additive candidate staging; never boots, flashes or loads modules.

Default prints a plan. --execute-authorized is required for board writes.
On any failure retain partial files/evidence. Never auto-delete or retry.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import tarfile
import time
import re
from original_module_backup import current_tree_matches, tree_digest

RELEASE = "6.8.12-a10irq1"
BOOT = "eb429b2f-66aa-4959-8610-bfcfabcf0202"
BACKUP_BOOT = BOOT
ZOCL_SHA = "2aa089c3967e8fa72480310fe2cc12aaa7d920135f5322d8596819835ca087cc"
MACHINE_SHA = "ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec"
SOURCE = Path("/home/ubuntu/a10-kernel-trial-20261020-v1")
MODULE_PARENT = Path("/usr/lib/modules")
BOOT_PARENT = Path("/boot/firmware")
FIT_NAME = "a10-candidate-20261020.fit"
PINNED = {
    "candidate.fit": (65552664, "a393f397a673a2f3636c8b9f85d8a59f7257c24d33c34d28a67b11c410a11b81"),
    "modules.tar.gz": (108698233, "c1ad278f7bcfc4137fc0013a98db593487ea5f22a1eff0acfddaf2e963255cf2"),
}
ORIGINAL = {
    "image.fit": "b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9",
    "boot.scr.uimg": "690fe1225a017a63796df1517b8b203fe9b7500597b2c5a61a0f524875ea2efc",
}
MAX_FILE = 32 * 1024**2
MAX_TOTAL = 512 * 1024**2
MAX_FILES = 6500
IO_RATE = 8 * 1024**2


def need(ok, why):
    if not ok:
        raise ValueError(why)


def regular(path):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode), "Nonregular or symlink file: " + str(path))
    return info


def digest(path):
    regular(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024**2), b""):
            h.update(block)
    return h.hexdigest()


def relative_member(member):
    name = member.name
    parts = PurePosixPath(name).parts
    prefix = ("lib", "modules", RELEASE)
    need(name and "\\" not in name and "\0" not in name and
         not name.startswith("/") and all(x not in ("", ".", "..") for x in name.split("/")),
         "Unsafe archive path")
    need(parts[:3] == prefix and len(parts) > 3, "Wrong module tree")
    need(member.isfile() and not member.issym() and not member.islnk(), "Only regular archive files")
    need(0 <= member.size <= MAX_FILE, "Member size cap")
    rel = PurePosixPath(*parts[3:])
    need(str(rel).endswith(".ko") or
         (len(rel.parts) == 1 and rel.name.startswith("modules.")), "Unexpected module-tree file")
    return rel


class Limiter:
    """Single-threaded modest IO rate; health callback also runs while pacing."""
    def __init__(self, rate=IO_RATE, health=lambda: None):
        self.rate, self.health = rate, health
        self.bytes, self.started, self.last_health = 0, time.monotonic(), float("-inf")

    def check_health(self):
        now = time.monotonic()
        if now - self.last_health >= 2:
            self.health()
            self.last_health = now

    def add(self, count):
        self.bytes += count
        wait = self.bytes / self.rate - (time.monotonic() - self.started)
        while wait > 0:
            time.sleep(min(wait, 0.25))
            self.check_health()
            wait = self.bytes / self.rate - (time.monotonic() - self.started)
        self.check_health()


def unpack_modules(archive, dest, limiter, expected_modules=6218):
    need(not dest.exists() and not dest.is_symlink(), "Module staging destination exists")
    dest.mkdir(mode=0o700)
    seen, total, modules, hashes = set(), 0, 0, {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            rel = relative_member(member)
            name = rel.as_posix()
            need(name not in seen, "Duplicate archive member")
            seen.add(name)
            total += member.size
            need(total <= MAX_TOTAL and len(seen) <= MAX_FILES, "Archive budget exceeded")
            target = dest.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Destination newly made by this process. Refuse any symlink in it.
            for parent in (target, *target.parents):
                if parent == dest.parent:
                    break
                need(not parent.is_symlink(), "Symlink in destination")
            h, written = hashlib.sha256(), 0
            with tar.extractfile(member) as src, target.open("xb") as out:
                while True:
                    block = src.read(1024**2)
                    if not block:
                        break
                    out.write(block); h.update(block); written += len(block)
                    limiter.add(len(block))
                out.flush()
            need(written == member.size, "Truncated archive member")
            target.chmod(0o644)
            hashes[name] = h.hexdigest()
            modules += name.endswith(".ko")
    need(modules == expected_modules, "Incomplete module set")
    for metadata in ("modules.dep", "modules.dep.bin", "modules.alias", "modules.alias.bin"):
        need(metadata in seen, "Missing module metadata: " + metadata)
    for p in dest.rglob("*"):
        if p.is_dir():
            p.chmod(0o755)
    # Read back every installed byte. Archive hash alone cannot attest SD writes.
    for name, expected in hashes.items():
        target = dest.joinpath(*PurePosixPath(name).parts)
        need(digest(target) == expected, "Staged file readback mismatch: " + name)
        limiter.add(target.stat().st_size)
    return {"files": len(seen), "modules": modules, "bytes": total,
            "readback_sha256": hashes}


def rename_noreplace(source, target):
    """Linux atomic no-clobber publication, no fallback to replacing rename."""
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renameat2
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def flush_filesystem(path):
    """Flush the filesystem containing the explicit candidate path, not all disks."""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        fn = libc.syncfs
        fn.argtypes = [ctypes.c_int]; fn.restype = ctypes.c_int
        if fn(fd) != 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(path))
    finally:
        os.close(fd)


def plan():
    return {"operation": "ADDITIVE_STAGE_ONLY_NOT_BOOT_OR_MODULE_LOAD",
            "source": str(SOURCE), "kernel_release": RELEASE,
            "candidate_fit": str(BOOT_PARENT / FIT_NAME),
            "candidate_modules": str(MODULE_PARENT / RELEASE),
            "original_boot_files": ORIGINAL, "pins": PINNED,
            "io_rate_bytes_s": IO_RATE, "max_unpacked_bytes": MAX_TOTAL,
            "failure": "RETAIN_PARTIALS_NO_DELETE_NO_RETRY_NO_BOOT",
            "required_backup_proof": str(SOURCE / "original-backup-proof.json"),
            "backup_proof_sha256": "REQUIRED_FROM_PC_VERIFIED_ORIGINAL_MODULE_BACKUP",
            "QSPI_write": False, "default_boot_change": False,
            "module_load": False, "compute": False}


def check_backup_proof(path, expected_sha256, old_root):
    need(isinstance(expected_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", expected_sha256),
         "Explicit pinned backup proof SHA256 required")
    need(regular(path).st_size <= 8 * 1024**2 and digest(path) == expected_sha256,
         "Backup proof hash/size mismatch")
    proof = json.loads(path.read_text())
    need(proof.get("schema") == "A10_ORIGINAL_MODULE_BACKUP_PROOF_V1" and
         proof.get("status") == "VERIFIED_PC_BACKUP" and proof.get("release") == "6.8.0-1015-xilinx",
         "Backup not verified")
    need(proof.get("identity") == {"boot_id": BACKUP_BOOT, "machine_sha256": MACHINE_SHA},
         "Backup is not for the explicitly pinned source board/boot")
    rows = proof.get("rows", [])
    need(rows and len(rows) == len({r["path"] for r in rows}) and
         tree_digest(rows) == proof.get("tree_sha256"), "Backup manifest invalid")
    need(any(r["path"] == "modules.dep" and r["kind"] == "file" for r in rows),
         "Backup metadata missing")
    current_tree_matches(old_root, proof)
    return proof


def run(backup_proof_sha256):
    need(os.geteuid() == 0 and platform.machine() == "aarch64", "Real board root required")
    need(platform.release() == "6.8.0-1015-xilinx", "Original kernel required for staging")
    need(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == BOOT, "Boot ID changed")
    need(digest(Path("/etc/machine-id")) == MACHINE_SHA, "Board identity mismatch")
    need(not Path("/sys/module/zocl").exists(), "ZOCL must be absent")
    need(Path("/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1").is_dir(),
         "Original default configuration required")
    need(MODULE_PARENT.resolve() == MODULE_PARENT and BOOT_PARENT.resolve() == BOOT_PARENT,
         "Unexpected target-parent symlink")
    need(SOURCE.resolve() == SOURCE, "Source directory symlink")
    mounts = subprocess.run(["findmnt", "-n", "-o", "SOURCE,FSTYPE", "--target", str(BOOT_PARENT)],
                            check=True, capture_output=True, text=True, timeout=3).stdout.split()
    need(mounts == ["/dev/mmcblk1p1", "vfat"], "Boot filesystem identity")
    need(shutil.disk_usage(BOOT_PARENT).free > 256 * 1024**2, "Boot filesystem margin")
    need(shutil.disk_usage(MODULE_PARENT).free > 2 * 1024**3, "Root filesystem margin")
    targets = [MODULE_PARENT / RELEASE, MODULE_PARENT / (".a10-" + RELEASE + ".partial"),
               BOOT_PARENT / FIT_NAME, BOOT_PARENT / (FIT_NAME + ".partial")]
    need(all(not p.exists() and not p.is_symlink() for p in targets), "Never overwrite target/partial")
    # This is deliberately before ANY candidate or receipt creation. The caller
    # must pin the PC verifier's proof, not just claim a backup step was done.
    check_backup_proof(SOURCE / "original-backup-proof.json", backup_proof_sha256,
                       MODULE_PARENT / "6.8.0-1015-xilinx")
    for name, expected in ORIGINAL.items():
        need(digest(BOOT_PARENT / name) == expected, "Original boot file changed")
    for name, (size, expected) in PINNED.items():
        need(regular(SOURCE / name).st_size == size and digest(SOURCE / name) == expected,
             "Input package pin mismatch")
    os.nice(19)
    receipt = SOURCE / "stage-result.jsonl"
    with receipt.open("x", encoding="utf-8") as log:
        def emit(event, **kw):
            row = {"event": event, "monotonic_s": time.monotonic(), **kw}
            line = json.dumps(row)
            log.write(line + "\n"); log.flush(); os.fsync(log.fileno())
            print(line, flush=True)

        def health():
            values = [int(p.read_text()) for p in Path("/sys/class/hwmon").glob("hwmon*/temp*_input")]
            mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
            avail = int(mem["MemAvailable"].split()[0])
            need(values and all(0 < n < 55000 for n in values), "Staging thermal guard")
            need(avail > 1024**2, "Keep at least 1GiB available")
            need(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == BOOT, "Boot changed")
            emit("HEALTH", temperatures_mC=values, MemAvailable_KiB=avail)

        try:
            health(); emit("BEGIN", plan=plan())
            result = unpack_modules(SOURCE / "modules.tar.gz", targets[1], Limiter(health=health))
            emit("MODULE_READBACK", **{k: v for k, v in result.items() if k != "readback_sha256"})
            with (SOURCE / "staged-module-hashes.json").open("x") as f:
                json.dump(result, f)
            need(digest(targets[1] / "extra/zocl.ko") == ZOCL_SHA, "ZOCL pin")
            targets[1].chmod(0o755)
            # Flush only the candidate filesystem via ordinary file operations.
            # No recursive removal and no writes into the old module release.
            rename_noreplace(targets[1], targets[0])
            flush_filesystem(MODULE_PARENT)
            emit("MODULES_PUBLISHED", target=str(targets[0]))
            limiter = Limiter(health=health)
            with (SOURCE / "candidate.fit").open("rb") as src, targets[3].open("xb") as dst:
                for block in iter(lambda: src.read(1024**2), b""):
                    dst.write(block); limiter.add(len(block))
                dst.flush(); os.fsync(dst.fileno())
            need(digest(targets[3]) == PINNED["candidate.fit"][1], "FIT readback mismatch")
            rename_noreplace(targets[3], targets[2])
            flush_filesystem(BOOT_PARENT)
            for name, expected in ORIGINAL.items():
                need(digest(BOOT_PARENT / name) == expected, "Original boot file changed after staging")
            health()
            emit("STAGED_ONLY_NOT_BOOTED", kernel_release=RELEASE,
                 original_boot_unchanged=True, candidate_boot="NOT_TESTED")
        except Exception as exc:
            emit("FAILED_PARTIALS_RETAINED_NO_BOOT", error=str(exc))
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-authorized", action="store_true")
    parser.add_argument("--backup-proof-sha256")
    args = parser.parse_args()
    if args.execute_authorized:
        run(args.backup_proof_sha256)
    else:
        print(json.dumps(plan(), indent=2))
