"""Offline configuration/contract validation; no library loading or downloads."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]


def safe_path(root, name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("Invalid relative path")
    parts = name.split("/")
    if PurePosixPath(name).is_absolute() or any(p in {"", ".", ".."} for p in parts):
        raise ValueError("Unsafe path")
    root = root.resolve()
    path = root.joinpath(*parts)
    if any(p.is_symlink() for p in [path, *path.parents] if p != root):
        raise ValueError("Symlink path")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Escaping path")
    return path


def validate(root, config, require_installed=False):
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported schema")
    model = config.get("model", {})
    if (model.get("repository"), model.get("mode"), model.get("thinking")) != ("Qwen/Qwen3.5-0.8B", "text", False):
        raise ValueError("Wrong model/mode")
    if config.get("auto_download_candidates") is not False or config.get("fallback") != "disabled":
        raise ValueError("Automatic download/fallback prohibited")
    if config.get("selection_time") != "startup_only_after_device_quiescence":
        raise ValueError("Unsafe backend switch policy")
    safe_path(root, model["asset_directory"])
    lock_path = safe_path(root, config["contract_lock"])
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    mapping = lock["files"]
    if set(mapping) != {"quant_v1.json", "sp_linear_v1.h", "voice_v1.json", "voice_examples.jsonl"}:
        raise ValueError("Unexpected contract inventory")
    digest = hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != lock["contract_sha256"]:
        raise ValueError("Invalid contract mapping digest")
    for name, expected in mapping.items():
        if hashlib.sha256(safe_path(lock_path.parent, name).read_bytes()).hexdigest() != expected:
            raise ValueError("Contract file changed: " + name)
    selected = {}
    for key, group, allowed in [("linear_backend", "backends", {"A", "B"}), ("voice_backend", "voices", {"A", "C"})]:
        owner = config.get(key)
        if owner not in allowed:
            raise ValueError("Unknown selection: " + key)
        # Unselected candidate directories are not opened or scanned.
        manifest = safe_path(root, config[group][owner])
        selected[key] = {"owner": owner, "manifest": config[group][owner],
                         "status": "PRESENT_UNVERIFIED" if manifest.is_file() else "NOT_IMPLEMENTED"}
    if require_installed:
        # A00 has no runtime loader; presence alone is never readiness.
        raise ValueError("Runtime readiness NOT_TESTED: module validation/loader not implemented in A00")
    return {"domain": "PC", "configuration": "PASS", "contract_sha256": digest,
            "selected": selected, "runtime": "NOT_TESTED", "board": "NOT_TESTED"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=ROOT / "config/qwen35/selection.json")
    p.add_argument("--require-installed", action="store_true")
    a = p.parse_args()
    try:
        result = validate(ROOT, json.loads(a.config.read_text(encoding="utf-8")), a.require_installed)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"configuration": "FAIL", "reason": str(exc)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
