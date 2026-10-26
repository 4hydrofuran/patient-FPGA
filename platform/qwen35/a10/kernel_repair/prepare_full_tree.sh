#!/usr/bin/env bash
# PC-only fresh source tree. No install, sudo, SSH, device or boot operations.
set -euo pipefail
test "$(uname -m)" = x86_64
repo=/mnt/c/Patientqwen
archives=$repo/platform/local/a10-kernel-refaudit-20261019
bundle=$repo/platform/build/a10-kernel-repair-20261019-v2
work=/home/member-a/a10-kernel-full-20261019-v1
test ! -e "$work"
test "$(sha256sum "$archives/linux-xilinx_6.8.0.orig.tar.gz" | cut -d ' ' -f1)" = 26512115972bdf017a4ac826cc7d3e9b0ba397d4f85cd330e4e4ff54c78061c8
test "$(sha256sum "$archives/linux-xilinx_6.8.0-1015.16.diff.gz" | cut -d ' ' -f1)" = 2f73ef45d2ddbb70e540fc657bf3c74a7c45d3b0663c10e0a6e45f723c332954
test "$(sha256sum "$bundle/repair.patch" | cut -d ' ' -f1)" = 9a3a695f0c45353ce7c5cfd920af9ccba46218820434372adde7af23d4190a89
mkdir -m 700 "$work"
mkdir "$work/source" "$work/build" "$work/logs" "$work/deps"
tar --no-same-owner -xzf "$archives/linux-xilinx_6.8.0.orig.tar.gz" --strip-components=1 -C "$work/source"
gzip -dc "$archives/linux-xilinx_6.8.0-1015.16.diff.gz" | patch --batch --forward --fuzz=0 -p1 -d "$work/source" > "$work/logs/ubuntu-package-patch.log"
python3 - "$bundle" "$work/source" <<'PY'
import hashlib,json,sys
from pathlib import Path
b,s=map(Path,sys.argv[1:])
m=json.loads((b/'manifest.json').read_text(encoding='utf-8'))
for name, row in m['files'].items():
    if hashlib.sha256((s/name).read_bytes()).hexdigest()!=row['original_sha256']:
        raise SystemExit('Source mismatch before candidate: '+name)
print('PASS: three complete-tree originals match audited originals')
PY
patch --batch --forward --fuzz=0 -p1 -d "$work/source" -i "$bundle/repair.patch" > "$work/logs/a10-repair-patch.log"
python3 - "$bundle" "$work/source" <<'PY'
import hashlib,json,sys
from pathlib import Path
b,s=map(Path,sys.argv[1:])
m=json.loads((b/'manifest.json').read_text(encoding='utf-8'))
for name, row in m['files'].items():
    if hashlib.sha256((s/name).read_bytes()).hexdigest()!=row['candidate_sha256']:
        raise SystemExit('Source mismatch after candidate: '+name)
print('PASS: three complete-tree candidates match tested candidate')
PY
sha256sum "$work/logs/ubuntu-package-patch.log" "$work/logs/a10-repair-patch.log"
printf 'SOURCE_STAGED_ONLY_NOT_BUILT_NOT_DEPLOYABLE\n'
