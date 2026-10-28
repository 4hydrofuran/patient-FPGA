"""Protect the fixed business rules and cases used by this integration."""

import hashlib
import json
from pathlib import Path


def test_reference_files_match_published_upstream_manifest():
    root = Path(__file__).resolve().parents[2]
    provenance = json.loads((root / "UPSTREAM.json").read_text(encoding="utf-8-sig"))
    assert provenance["commit"] == "9276b4a33084325ec2a72c12f99a6fbb91bbfe1c"
    for entry in provenance["files"]:
        data = (root / entry["local"]).read_bytes()
        assert len(data) == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]

