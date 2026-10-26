#!/usr/bin/env bash
# PC-only non-mutating validation of the saved patch and source hashes.
set -euo pipefail
test "$(uname -m)" = x86_64
bundle=/mnt/c/Patientqwen/platform/build/a10-kernel-repair-20261019-v2
patch --batch --dry-run --forward --fuzz=0 -p1 -d "$bundle/original" -i "$bundle/repair.patch"
patch --batch --dry-run --reverse --fuzz=0 -p1 -d "$bundle/candidate" -i "$bundle/repair.patch"
python3 - "$bundle" <<'PY'
import hashlib
import json
import sys
from pathlib import Path
b = Path(sys.argv[1])
m = json.loads((b / 'manifest.json').read_text(encoding='utf-8'))
def verify(p, expected):
    if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise SystemExit('SHA mismatch: ' + str(p))
verify(b / 'repair.patch', m['patch_sha256'])
for name, hashes in m['files'].items():
    verify(b / 'original' / name, hashes['original_sha256'])
    verify(b / 'candidate' / name, hashes['candidate_sha256'])
print('PASS: patch and six source SHA256 values; dry-run did not modify sources')
PY
