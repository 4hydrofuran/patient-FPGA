#!/usr/bin/env bash
# PC compile/API check against already verified old headers, NOT for board use.
set -euo pipefail
test "$(uname -m)" = x86_64
umask 077
repo=/mnt/c/Patientqwen
out=/home/member-a/a10-driver-irq-oldabi-PC-20261019-v1
kernel=/home/member-a/a10-driver-audit-20261018/headers/usr/src/linux-headers-6.8.0-1015-xilinx
package="$repo/platform/local/a10-xrt-2.18-audit/xrt-dkms_2.18.0-0ubuntu1_arm64.deb"
test "$(sha256sum "$package" | cut -d ' ' -f1)" = 096cb3c25a2f6885bfc615746aba0cdcd74075b724207f0e02ba3dc05ba54297
test "$(sha256sum "$kernel/.config" | cut -d ' ' -f1)" = 6ebb559a50a68b26bd0a681ea010264525af09cc4faa7814abfc0a1ddd20ff2e
test "$(sha256sum "$kernel/Module.symvers" | cut -d ' ' -f1)" = 7e93bbb17224ef84a9641c4fca7481323adf5dca4b3f46329327707003a818b3
mkdir "$out"
dpkg-deb -x "$package" "$out"
driver="$out/usr/src/xrt-2.18.0/driver/zocl"
python3 "$repo/platform/qwen35/a10/kernel_repair/apply_driver_candidate.py" \
  --bundle "$repo/platform/build/a10-driver-irq-repair-20261019-v1" --source "$driver"
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS
cd "$driver"
timeout 180s nice -n 10 make -j2 KERNEL_SRC="$kernel" ARCH=arm64 CROSS_COMPILE=aarch64-amd-linux- \
  CC=aarch64-amd-linux-gcc HOSTCC=/usr/bin/gcc GIT_HASH=debian-xrt-2.18.0-0ubuntu1 \
  GIT_HASH_DATE=package-source GIT_BRANCH=A10-local-IRQ-candidate \
  GIT_MODIFIED_FILES=common/cu.c,zert/zocl_xgq_intc.c DATE_NOW=2026-10-19 modules
python3 "$repo/platform/qwen35/a10/audit_zocl_module.py" "$driver/zocl.ko" "$kernel/Module.symvers" --output "$out/oldabi-audit-PC-ONLY.json"
printf 'OLD_ABI_PC_COMPILE_ONLY_NOT_NEW_KERNEL_MODULE_NOT_DEPLOYABLE\n'
