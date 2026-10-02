#!/usr/bin/env python3
"""Read-only candidate manifest/hash checker. Never executes candidate code.
Does not certify authenticity, functionality, safety or board performance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
HEX = re.compile(r"[0-9a-f]{64}\Z")
STATUSES = {"NOT_TESTED", "PASS", "FAIL", "NOT_APPLICABLE"}
def fail(message: str) -> None:
    raise ValueError(message)
def safe_file(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\\" in name:
        fail("Invalid relative file path")
    pp = PurePosixPath(name)
    if pp.is_absolute() or any(p in {"..", ".", ""} for p in name.split("/")):
        fail(f"Unsafe path: {name}")
    path = root.joinpath(*pp.parts)
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            fail(f"Symlink is not allowed: {name}")
    if not path.is_file() or not path.resolve().is_relative_to(root):
        fail(f"Missing/escaping file: {name}")
    return path

def check_bundle(root: Path, contract_path: Path, require_board: bool = False) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        fail("Bundle path must be a directory")
    mf = safe_file(root, "manifest.json")
    m = json.loads(mf.read_text(encoding="utf-8"))
    lock = json.loads(contract_path.read_text(encoding="utf-8"))
    expected = lock.get("contract_sha256")
    if not isinstance(expected, str) or not HEX.fullmatch(expected):
        fail("Invalid expected contract digest")
    # Verify the supplied lock's own canonical file list and actual contract files.
    files_lock = lock.get("files")
    if not isinstance(files_lock, dict) or not files_lock:
        fail("Contract lock must declare nonempty files")
    canonical = json.dumps(files_lock, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != expected:
        fail("Contract lock digest is inconsistent")
    contract_root = contract_path.parent.resolve()
    for name, digest in files_lock.items():
        p = safe_file(contract_root, name)
        if hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            fail(f"Local contract changed: {name}")
    if m.get("schema_version") != 1 or m.get("module_type") not in {"linear", "voice"}:
        fail("Unsupported manifest schema/module_type")
    if m.get("contract_sha256") != expected:
        fail("Contract digest mismatch")
    if not m.get("module_id") or not m.get("source_commit"):
        fail("Missing module_id or source_commit")
    entries = m.get("files")
    if not isinstance(entries, list) or not entries:
        fail("No declared files")
    seen = set()
    for item in entries:
        if not isinstance(item, dict):
            fail("Invalid file record")
        name = item.get("path")
        p = safe_file(root, name)
        if name in seen or name == "manifest.json":
            fail("Duplicate file or self-hashed manifest")
        seen.add(name)
        digest = item.get("sha256")
        if not isinstance(digest, str) or not HEX.fullmatch(digest):
            fail(f"Invalid digest: {name}")
        if p.stat().st_size != item.get("bytes"):
            fail(f"File size mismatch: {name}")
        with p.open("rb") as f:
            h = hashlib.file_digest(f, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else None
        if h is None:
            hs = hashlib.sha256()
            with p.open("rb") as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    hs.update(block)
            h = hs.hexdigest()
        if h != digest:
            fail(f"File digest mismatch: {name}")
    actual = set()
    for p in root.rglob("*"):
        if p.is_symlink():
            fail(f"Symlink in bundle: {p}")
        if p.is_file() and p.name != "manifest.json":
            actual.add(p.relative_to(root).as_posix())
    # A nested manifest.json is still a normal file and must be declared.
    for p in root.rglob("manifest.json"):
        if p != mf:
            actual.add(p.relative_to(root).as_posix())
    if actual != seen:
        fail(f"Undeclared/missing files: {sorted(actual ^ seen)[:10]}")
    ep = m.get("entrypoints", {})
    required = {"selftest", "library" if m["module_type"] == "linear" else "worker"}
    for key in required:
        if ep.get(key) not in seen:
            fail(f"Undeclared entrypoint: {key}")
    tests = m.get("tests")
    if not isinstance(tests, dict) or "board" not in tests:
        fail("Missing explicit board test status")
    for name, result in tests.items():
        if not isinstance(result, dict) or result.get("status") not in STATUSES:
            fail(f"Invalid test status: {name}")
        ev = result.get("evidence", [])
        if not isinstance(ev, list) or any(e not in seen for e in ev):
            fail(f"Missing declared test evidence: {name}")
        if result["status"] == "PASS" and not ev:
            fail(f"PASS without evidence: {name}")
    if require_board:
        if tests["board"]["status"] != "PASS" or not m.get("board_identity"):
            fail("Board pass/identity evidence required")
    return {"module_id": m["module_id"], "static_integrity": "PASS",
            "board_claim": tests["board"]["status"],
            "warning": "Static check only; does not establish real board execution or performance."}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--require-board", action="store_true")
    args = parser.parse_args()
    try:
        result = check_bundle(args.bundle, args.contract, args.require_board)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
