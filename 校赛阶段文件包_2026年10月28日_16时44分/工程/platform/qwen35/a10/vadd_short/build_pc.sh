#!/usr/bin/env bash
# PC only. Native control tests + actual ARM64 cross-link against extracted XRT 2.18.
set -euo pipefail
repo=/mnt/c/Patientqwen
out=${1:?new absolute output directory}
[[ "$out" = /* && ! -e "$out" && ! -L "$out" ]]
mkdir "$out"
src="$repo/platform/qwen35/a10/vadd_short"
xrt=/home/member-a/a10-driver-audit-20261018/xrt-userspace
test -f "$xrt/usr/include/xrt/xrt/xrt_kernel.h"
test -f "$xrt/usr/lib/libxrt_coreutil.so.2.18.0"
cp "$src/host.cpp" "$src/control.hpp" "$src/retention.hpp" "$src/test_control.cpp" "$src/test_retention.cpp" "$src/approval.pending.json" "$out/"
set -x
if [[ "${2:-all}" != 'arm-only' ]]; then
g++ -std=c++17 -O2 -Wall -Wextra -Werror "$src/test_control.cpp" -o "$out/control-test"
"$out/control-test"
g++ -std=c++17 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -no-pie "$src/test_control.cpp" -o "$out/control-test-san"
ASAN_OPTIONS=detect_leaks=1 "$out/control-test-san"
g++ -std=c++17 -O2 -Wall -Wextra -Werror "$src/test_retention.cpp" -pthread -o "$out/retention-test"
"$out/retention-test"
fi
set +x
set +u
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
read -r -a compiler <<< "$CXX"
set -x
"${compiler[@]}" -mcpu=cortex-a53 -mbranch-protection=none -std=c++17 -O2 -Wall -Wextra -Werror \
    -I"$xrt/usr/include/xrt" -I"$repo/platform/local/qwen35/llama.cpp-81e39ad34368329b5db77620721510fd91107e80/vendor/nlohmann" \
    "$src/host.cpp" -L"$xrt/usr/lib" -lxrt_coreutil -luuid -lcrypto -pthread -Wl,-z,defs -o "$out/a10-vadd-short"
"$READELF" -h -d -V "$out/a10-vadd-short"
sha256sum "$out/a10-vadd-short" "$src/host.cpp" "$src/control.hpp" "$src/retention.hpp" \
    "$xrt/usr/lib/libxrt_coreutil.so.2.18.0" "$xrt/usr/lib/libxrt_core.so.2.18.0" "$xrt/usr/include/xrt/xrt/xrt_kernel.h"
set +x
printf '%s\n' 'CROSS_BUILD_ONLY_NOT_BOARD; no ARM binary executed, no device access.'
