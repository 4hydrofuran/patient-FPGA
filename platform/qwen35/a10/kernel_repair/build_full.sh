#!/usr/bin/env bash
# PC-only build. No total time limit after the user's 2026-10-19 instruction.
# All output, including generated signing key, stays local.
set -euo pipefail
source /mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/full_build_env.sh
umask 077
attempt=${1:-01}
case "$attempt" in 01|02|03) ;; *) printf 'Unreviewed build attempt\n' >&2; exit 2;; esac
exec 9> "$work/full-build.lock"
flock -n 9
if [ "$attempt" != 01 ]; then
  python3 - "$attempt" <<'PY'
import json
import sys
from pathlib import Path
previous = {'02': '01', '03': '02'}[sys.argv[1]]
p = Path('/mnt/c/Patientqwen/evidence/board_platform/A10_20261018_intake') / f'kernel_full_build_{previous}.json'
assert json.loads(p.read_text())['exit_code'] == 124, 'Resume only the recorded timed-out build'
PY
fi
test "$(sha256sum "$work/build/.config" | cut -d ' ' -f1)" = 97a9a28a66ae1466f07667b2c75ab2d3dce0c1451cd51923a3c2bc54ccf2aa8b
test "$(make -s "${build_args[@]}" kernelrelease)" = 6.8.12-a10irq1
log=$work/logs/full-build-$attempt.log
test ! -e "$log"
set -o noclobber
set +e
nice -n 10 make "${build_args[@]}" -j8 Image modules dtbs > "$log" 2>&1
result=$?
set -e
printf 'PC_FULL_BUILD_EXIT=%s\n' "$result"
tail -n 40 "$log"
sha256sum "$log"
test "$result" = 0 || exit "$result"
test "$(sha256sum "$work/build/.config" | cut -d ' ' -f1)" = 97a9a28a66ae1466f07667b2c75ab2d3dce0c1451cd51923a3c2bc54ccf2aa8b
sha256sum "$work/build/arch/arm64/boot/Image" "$work/build/Module.symvers" "$work/build/System.map"
printf 'FULL_BUILD_ONLY_NOT_INSTALLED_NOT_BOARD_ACCEPTED\n'
