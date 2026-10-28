"""Validate independent read-only upload evidence; do not retry transfer."""
import json
from pathlib import Path
from upload_candidate import ROOT, OUT, REMOTE

def validate(previous, diagnosis):
    if diagnosis["exit_code"] != 0 or diagnosis["board_writes"] is not False:
        raise ValueError("Invalid read-only result")
    rows = json.loads(diagnosis["stdout"])
    targets = [r for r in rows if r["path"] == REMOTE]
    if len(targets) != 1:
        raise ValueError("Exact destination missing/duplicated")
    row = targets[0]
    if row["symlink"] or not row["directory"]:
        raise ValueError("Unsafe destination")
    files = row["files"]
    actual = {f["name"]: f.get("sha256") for f in files if not f["symlink"]}
    if len(files) != len(actual) or actual != previous["hashes"]:
        raise ValueError("Upload content mismatch")
    return dict(status="UPLOADED_HASH_VERIFIED_NOT_INSTALLED", hashes=actual,
                evidence="upload_path_diagnosis_01.json", original_upload_exit=1,
                recovered_by="INDEPENDENT_READONLY_HASH_CHECK_NO_RETRANSFER",
                extra_empty_directory_retained="/home/ubuntu/homeubuntua10-kernel-trial-20261020-v1")

if __name__ == "__main__":
    result = validate(json.loads((OUT / "upload.json").read_text()),
                      json.loads((ROOT / "evidence/board_platform/A10_20261018_intake/upload_path_diagnosis_01.json").read_text()))
    with (OUT / "upload-readback.json").open("x") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result))
