"""Read-only artifact verification after v2 closeout; no board/model calls."""
import datetime
import hashlib
import json
from pathlib import Path

from tt10_01_common import ROOT, OUT, save


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    execution = OUT / "window-20261025-v2/execution-01"
    destination = execution / "FINAL_AUDIT.json"
    assert not destination.exists()
    summary = read(execution / "SUMMARY.json")
    assert summary["task01_complete"] is False
    assert summary["compute_pass"] is False
    assert summary["new_PL_calls"] == 0 and summary["TTFT_board_s"] is None
    assert summary["real_board_CPU_failure_close"]["status"] == "PASS_THIS_FAILURE_PATH_ONLY"
    inventory = read(execution / "READBACK_FILES.json")
    assert len(inventory["files"]) == 473
    for name, expected in inventory["files"].items():
        path = execution / "readback-01" / name
        assert path.stat().st_size == expected["bytes"] and digest(path) == expected["sha256"], name
    v3 = OUT / "window-20261025-v3"
    prepared = read(v3 / "PREPARED.json")
    bundle = v3 / prepared["local_bundle"]
    assert digest(bundle / "manifest.json") == prepared["bundle_manifest_sha256"]
    assert digest(v3 / "board_driver_plan.py") == prepared["driver_sha256"]
    manifest = read(bundle / "manifest.json")
    for expected in manifest["files"]:
        path = bundle / expected["path"]
        assert path.stat().st_size == expected["bytes"] and digest(path) == expected["sha256"], expected["path"]
    assert not list(bundle.rglob("*.pyc"))
    assert prepared["authorization_included"] is False
    assert prepared["deployed"] is False and prepared["executed"] is False
    numeric = Path("platform/qwen35/a12/tt10_01_numeric.py")
    assert digest(bundle / numeric) == digest(OUT / "window-20261025-v2/bundle-v3" / numeric)
    receipt = read(execution / "SHARED_STATUS_RECEIPT.json")
    for name, hashes in receipt["files"].items():
        assert digest(ROOT / name) == hashes["after_sha256"], name
    before = read(execution / "shared-before/docs/PROJECT_STATUS.json")
    after = read(ROOT / "docs/PROJECT_STATUS.json")
    key = "a12_ttft10_01_in_progress_20261025"
    assert {k: v for k, v in before.items() if k != key} == {k: v for k, v in after.items() if k != key}
    for name in ("window02_contracts_final_01", "window02_config_final_01"):
        assert read(OUT / "logs" / (name + ".json"))["exit_code"] == 0
    result = dict(status="PASS_ARTIFACT_INTEGRITY_ONLY", updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  readback_files_verified=473, v3_manifest_files_verified=len(manifest["files"]),
                  generic_numeric_unchanged=True, other_project_status_entries_unchanged=True,
                  governance_checks="PASS_PC_ONLY", original_failure_preserved=True,
                  task01_complete=False, new_PL_calls=0, TTFT_board_s=None,
                  v3_executed=False, authentication_session="CLOSED_REQUESTS_10_SECRET_NOT_PERSISTED",
                  model_runs=0, board_contact=False)
    save(destination, result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
