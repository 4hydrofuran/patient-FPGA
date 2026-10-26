#!/usr/bin/env bash
# PC cross build only. No SSH, serial, board discovery, rootfs install or ARM execution.
set -euo pipefail
repo=/mnt/c/Patientqwen
work=$1
test -d "$work/derived"
test ! -e "$work/libsp_linear_a11_trial.so"
set +u
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
xrt218=/home/member-a/a10-driver-audit-20261018/xrt-userspace/usr
test -f "$xrt218/include/xrt/xrt/xrt_device.h"
read -r -a compiler <<< "$CXX"
set -x
"${compiler[@]}" -mcpu=cortex-a53 -std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror -fPIC -shared \
  -I"$xrt218/include/xrt" -I"$repo/contracts/qwen35" -I"$repo/modules/linear_A/xrt" \
  -I"$repo/release/a07_b04_v3/third_party/nlohmann" -I"$repo/platform/qwen35/a11" \
  "$work/derived/backend.cpp" "$repo/modules/linear_A/xrt/host_contract.cpp" \
  "$xrt218/lib/libxrt_coreutil.so.2.18.0" -luuid -lcrypto -pthread -Wl,-z,defs \
  -Wl,-soname,libsp_linear_a11_trial.so -o "$work/libsp_linear_a11_trial.so"
"$READELF" -h -d -V --wide "$work/libsp_linear_a11_trial.so"
sha256sum "$work/libsp_linear_a11_trial.so"
