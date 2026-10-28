#!/usr/bin/env bash
# Install into a NEW private PC staging tree, never into the host/board system.
set -euo pipefail
source /mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/full_build_env.sh
umask 077
python3 - <<'PY'
import json
from pathlib import Path
base=Path('/mnt/c/Patientqwen/evidence/board_platform/A10_20261018_intake')
for name in ['kernel_full_build_02.json','kernel_full_zocl_build_01.json']:
    assert json.loads((base/name).read_text())['exit_code']==0, 'Missing complete build: '+name
PY
stage="$work/module-stage-v2"
test ! -e "$stage"
test "$(readlink -m "$stage")" = /home/member-a/a10-kernel-full-20261019-v1/module-stage-v2
test "$(make -s "${build_args[@]}" kernelrelease)" = 6.8.12-a10irq1
test "$(sha256sum "$work/build/.config" | cut -d ' ' -f1)" = 97a9a28a66ae1466f07667b2c75ab2d3dce0c1451cd51923a3c2bc54ccf2aa8b
# v1 is retained: make returned 0 despite a non-executable Ubuntu policy helper.
# Restore ONLY that known helper's execute bit, without changing its bytes.
helper="$work/source/debian/scripts/sign-module"
test "$(sha256sum "$helper" | cut -d ' ' -f1)" = 712d7ad2c2e92ef519d06c51bfa16aa1d499dfb73880cc3d8c40bbba97a7f549
chmod u+x "$helper"
test -x "$helper"
mkdir -m 700 "$stage"
log="$work/logs/module-stage-v2.log"
set -o noclobber
# Kbuild removes only the not-yet-existing kernel/build entries in this NEW tree.
nice -n 10 make "${build_args[@]}" -j4 INSTALL_MOD_PATH="$stage" \
  INSTALL_MOD_STRIP=1 DEPMOD=/usr/sbin/depmod modules_install > "$log" 2>&1
if grep -E 'Permission denied|not found|Error [0-9]' "$log"; then exit 1; fi
driver="$work/zocl-source-v1/usr/src/xrt-2.18.0/driver/zocl"
target="$stage/lib/modules/6.8.12-a10irq1/extra"
mkdir "$target"
cp "$driver/zocl.ko" "$target/zocl.ko"
aarch64-amd-linux-strip --strip-debug "$target/zocl.ko"
# Only the module and public signer identity leave this directory, never keys.
"$work/build/scripts/sign-file" sha512 "$work/build/certs/signing_key.pem" \
  "$work/build/certs/signing_key.x509" "$target/zocl.ko"
/usr/sbin/depmod -b "$stage" 6.8.12-a10irq1
python3 /mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/audit_full_zocl.py \
  "$target/zocl.ko" "$work/build" --output "$work/zocl-staged-audit-v2.json"
python3 /mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/audit_module_stage.py \
  --stage "$stage" --kernel "$work/build" --source "$work/source" \
  --output "$work/module-stage-audit-v2.json"
/usr/sbin/modinfo -F vermagic "$target/zocl.ko"
/usr/sbin/modinfo -F signer "$target/zocl.ko"
sha256sum "$log" "$target/zocl.ko"
printf 'PRIVATE_PC_STAGING_ONLY_NO_SYSTEM_INSTALL_NO_BOARD_ACCESS\n'
