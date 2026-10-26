#!/usr/bin/env bash
set -euo pipefail
source /mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/full_build_env.sh
umask 077
test ! -e "$work/build/.config"
orig=/home/member-a/a10-driver-audit-20261018/headers/usr/src/linux-headers-6.8.0-1015-xilinx/.config
test "$(sha256sum "$orig" | cut -d ' ' -f1)" = 6ebb559a50a68b26bd0a681ea010264525af09cc4faa7814abfc0a1ddd20ff2e
cp "$orig" "$work/build/.config"
cp "$orig" "$work/config.original"
"$work/source/scripts/config" --file "$work/build/.config" --set-str LOCALVERSION '-a10irq1' \
  --set-str VERSION_SIGNATURE 'A10 local candidate; source Ubuntu linux-xilinx 6.8.0-1015.16; NOT_BOARD_ACCEPTED'
make "${build_args[@]}" olddefconfig
"$work/source/scripts/diffconfig" "$work/config.original" "$work/build/.config"
make -s "${build_args[@]}" kernelrelease
sha256sum "$work/build/.config"
printf 'CONFIGURED_ONLY_FULL_BUILD_AND_BOARD_PENDING\n'
