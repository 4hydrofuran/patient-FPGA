#!/usr/bin/env bash
# PC only. New exact-source extraction and new-kernel build; never insmod/install.
set -euo pipefail
source /mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/full_build_env.sh
umask 077
test -s "$work/build/arch/arm64/boot/Image"
test -s "$work/build/Module.symvers"
python3 - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('/mnt/c/Patientqwen/evidence/board_platform/A10_20261018_intake/kernel_full_build_02.json').read_text())
assert r['exit_code'] == 0, 'Complete-kernel success receipt required'
PY
package=/mnt/c/Patientqwen/platform/local/a10-xrt-2.18-audit/xrt-dkms_2.18.0-0ubuntu1_arm64.deb
test "$(sha256sum "$package" | cut -d ' ' -f1)" = 096cb3c25a2f6885bfc615746aba0cdcd74075b724207f0e02ba3dc05ba54297
mkdir "$work/zocl-source-v1"
dpkg-deb -x "$package" "$work/zocl-source-v1"
driver="$work/zocl-source-v1/usr/src/xrt-2.18.0/driver/zocl"
python3 /mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/apply_driver_candidate.py \
  --bundle /mnt/c/Patientqwen/platform/build/a10-driver-irq-repair-20261019-v1 --source "$driver"
cd "$driver"
nice -n 10 make -j2 KERNEL_SRC="$work/build" ARCH=arm64 CROSS_COMPILE=aarch64-amd-linux- \
  CC=aarch64-amd-linux-gcc HOSTCC=/usr/bin/gcc PAHOLE="$deps/usr/bin/pahole" \
  GIT_HASH=debian-xrt-2.18.0-0ubuntu1 GIT_HASH_DATE=package-source \
  GIT_BRANCH=A10-local-IRQ-candidate GIT_MODIFIED_FILES=common/cu.c,zert/zocl_xgq_intc.c DATE_NOW=2026-10-19 modules
file zocl.ko
python3 /mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/audit_full_zocl.py \
  "$driver/zocl.ko" "$work/build" --output "$work/zocl-audit-v1.json"
printf 'PC_MATCHED_DRIVER_ONLY_NOT_INSTALLED_OR_LOADED\n'
