"""Read-only board module exporter and PC streaming verifier. No installation.

Board export writes an uncompressed tar to stdout, never a board file.
PC verify writes proof exclusively, after checking every file against the
embedded manifest. The proof must be pinned separately before candidate staging.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import sys
import tarfile
import time

OLD = "6.8.0-1015-xilinx"
ROOT = Path("/usr/lib/modules") / OLD
BOOT = "eb429b2f-66aa-4959-8610-bfcfabcf0202"
MACHINE = "ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec"
PREFIX = "original-modules/" + OLD + "/"
MANIFEST = "A10_ORIGINAL_MODULES_MANIFEST.json"
MAX_BYTES = 256 * 1024**2
MAX_FILES = 10000
BUILD_TARGET = "/usr/src/linux-headers-" + OLD


def need(ok, why):
    if not ok:
        raise ValueError(why)


def tree_digest(rows):
    data = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def safe_relative(name):
    need(name.startswith(PREFIX), "Outside original module tree")
    rel = name[len(PREFIX):]
    need(rel and "\\" not in rel and "\0" not in rel and
         all(x not in ("", ".", "..") for x in rel.split("/")), "Unsafe module path")
    return rel


def board_health():
    need(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == BOOT, "Boot changed")
    values = [int(p.read_text()) for p in Path("/sys/class/hwmon").glob("hwmon*/temp*_input")]
    need(values and all(0 < t < 55000 for t in values), "Backup thermal guard")
    need(not Path("/sys/module/zocl").exists(), "Active ZOCL refused")


class HashReader:
    def __init__(self, file, tick):
        self.file, self.tick = file, tick
        self.hash = hashlib.sha256()

    def read(self, n):
        data = self.file.read(n)
        self.hash.update(data); self.tick(len(data))
        return data


def export_tree(root, output, identity, tick=lambda n: None):
    need(root.is_dir() and not root.is_symlink(), "Original root must be a real directory")
    rows, total = [], 0
    # Path.rglob does not descend through directory symlinks. lstat below is
    # authoritative; the only permitted symlink is recorded, never followed.
    with tarfile.open(fileobj=output, mode="w|") as tar:
        for path in sorted(root.rglob("*")):
            before = path.lstat()
            if stat.S_ISDIR(before.st_mode):
                continue
            rel = path.relative_to(root).as_posix()
            safe_relative(PREFIX + rel)
            need(len(rows) < MAX_FILES, "File count limit")
            info = tarfile.TarInfo(PREFIX + rel)
            info.mode = stat.S_IMODE(before.st_mode)
            info.uid, info.gid, info.mtime = before.st_uid, before.st_gid, int(before.st_mtime)
            row = {"path": rel, "mode": info.mode, "uid": info.uid, "gid": info.gid}
            if stat.S_ISLNK(before.st_mode):
                target = os.readlink(path)
                need(rel == "build" and target == BUILD_TARGET, "Unexpected source symlink")
                info.type, info.linkname = tarfile.SYMTYPE, target
                row.update(kind="symlink", target=target)
                tar.addfile(info)
            else:
                need(stat.S_ISREG(before.st_mode), "Unexpected source special file")
                total += before.st_size
                need(total <= MAX_BYTES, "Source byte limit")
                info.size = before.st_size
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                with os.fdopen(os.open(path, flags), "rb") as src:
                    opened = os.fstat(src.fileno())
                    need((opened.st_ino, opened.st_dev, opened.st_size, opened.st_mtime_ns) ==
                         (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns),
                         "Source changed before read")
                    reader = HashReader(src, tick)
                    tar.addfile(info, reader)
                    after = os.fstat(src.fileno())
                    need((after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
                         (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns),
                         "Source changed during read")
                row.update(kind="file", bytes=info.size, sha256=reader.hash.hexdigest())
            rows.append(row)
        need(rows and any(r["path"] == "modules.dep" for r in rows), "Missing module metadata")
        manifest = {"schema": "A10_ORIGINAL_MODULE_EXPORT_V1", "identity": identity,
                    "release": OLD, "bytes": total, "rows": rows, "tree_sha256": tree_digest(rows),
                    "source_writes": False, "symlink_targets_read": False}
        raw = json.dumps(manifest, sort_keys=True).encode()
        info = tarfile.TarInfo(MANIFEST); info.size = len(raw); info.mode = 0o600
        tar.addfile(info, io.BytesIO(raw))
    return manifest


def verify_archive(path):
    rows, seen, total, manifest = [], set(), 0, None
    with tarfile.open(path, "r:") as tar:
        for member in tar:
            need(member.name not in seen, "Duplicate archive member")
            seen.add(member.name)
            if member.name == MANIFEST:
                need(member.isfile() and member.size <= 8 * 1024**2, "Invalid manifest")
                manifest = json.load(tar.extractfile(member))
                continue
            need(manifest is None, "Data after manifest")
            rel = safe_relative(member.name)
            need(len(rows) < MAX_FILES, "Archive count limit")
            row = {"path": rel, "mode": member.mode, "uid": member.uid, "gid": member.gid}
            if member.issym():
                need(rel == "build" and member.linkname == BUILD_TARGET, "Unexpected archive symlink")
                row.update(kind="symlink", target=member.linkname)
            else:
                need(member.isfile() and member.size <= MAX_BYTES, "Nonregular archive entry")
                total += member.size
                need(total <= MAX_BYTES, "Archive byte limit")
                h = hashlib.sha256()
                with tar.extractfile(member) as src:
                    for block in iter(lambda: src.read(1024**2), b""):
                        h.update(block)
                row.update(kind="file", bytes=member.size, sha256=h.hexdigest())
            rows.append(row)
    need(manifest is not None and manifest.get("schema") == "A10_ORIGINAL_MODULE_EXPORT_V1",
         "Missing/unknown manifest")
    need(manifest["identity"] == {"boot_id": BOOT, "machine_sha256": MACHINE}, "Wrong source board/boot")
    need(manifest["release"] == OLD and manifest["source_writes"] is False and
         manifest["symlink_targets_read"] is False, "Unexpected source scope")
    need(manifest["rows"] == rows and manifest["bytes"] == total and
         manifest["tree_sha256"] == tree_digest(rows), "Backup data/manifest mismatch")
    need(any(r["path"] == "modules.dep" and r["kind"] == "file" for r in rows), "Missing metadata")
    archive_hash = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024**2), b""):
            archive_hash.update(block)
    return {"schema": "A10_ORIGINAL_MODULE_BACKUP_PROOF_V1", "status": "VERIFIED_PC_BACKUP",
            "identity": manifest["identity"], "release": OLD, "rows": rows,
            "tree_sha256": tree_digest(rows), "payload_bytes": total,
            "archive_bytes": path.stat().st_size, "archive_sha256": archive_hash.hexdigest(),
            "build_link_recorded_not_dereferenced": True, "board_restoration": "NOT_TESTED"}


def current_tree_matches(root, proof):
    """Ensure the PC-verified backup still matches every current board file."""
    need(root.is_dir() and not root.is_symlink(), "Original root must be a real directory")
    expected = {r["path"]: r for r in proof["rows"]}
    found = set()
    for path in root.rglob("*"):
        st = path.lstat()
        if stat.S_ISDIR(st.st_mode):
            continue
        rel = path.relative_to(root).as_posix()
        need(rel in expected, "Original module tree acquired an unbacked file")
        found.add(rel); row = expected[rel]
        need((stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid) ==
             (row["mode"], row["uid"], row["gid"]), "Original file metadata changed")
        if row["kind"] == "symlink":
            need(stat.S_ISLNK(st.st_mode) and os.readlink(path) == row["target"], "Link changed")
        else:
            need(stat.S_ISREG(st.st_mode) and st.st_size == row["bytes"], "Original file type/size changed")
            h = hashlib.sha256()
            with path.open("rb") as file:
                for block in iter(lambda: file.read(1024**2), b""):
                    h.update(block)
            need(h.hexdigest() == row["sha256"], "Original module contents changed")
    need(found == set(expected), "Original module file missing")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stream-readonly", action="store_true")
    p.add_argument("--verify", type=Path)
    p.add_argument("--proof", type=Path)
    a = p.parse_args()
    if a.stream_readonly:
        need(not a.verify and not a.proof, "Export cannot write board proof")
        need(platform.machine() == "aarch64" and platform.release() == OLD, "Wrong board platform")
        need(hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest() == MACHINE, "Wrong board")
        board_health()
        started, sent, last_check = time.monotonic(), [0], [0.0]
        def tick(count):
            sent[0] += count
            wait = sent[0] / (8 * 1024**2) - (time.monotonic() - started)
            if wait > 0:
                time.sleep(wait)
            if time.monotonic() - last_check[0] > 2:
                board_health(); last_check[0] = time.monotonic()
        export_tree(ROOT, sys.stdout.buffer, {"boot_id": BOOT, "machine_sha256": MACHINE}, tick)
    elif a.verify:
        need(a.proof is not None and not a.proof.exists(), "Exclusive proof output required")
        result = verify_archive(a.verify)
        with a.proof.open("x") as out:
            json.dump(result, out, indent=2)
        print(json.dumps({k: v for k, v in result.items() if k != "rows"}))
    else:
        print(json.dumps({"mode": "PLAN_ONLY", "source": str(ROOT), "board_writes": False,
                          "export": "uncompressed stdout tar; no secrets/source links followed"}))
