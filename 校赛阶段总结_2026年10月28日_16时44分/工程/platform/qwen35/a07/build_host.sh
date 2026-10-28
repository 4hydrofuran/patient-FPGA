#!/usr/bin/env bash
set -euo pipefail
repo=/mnt/c/Patientqwen
test ! -e host-test
python3 "$repo/platform/qwen35/a07/snapshot_build.py" "$PWD"
flags=(-std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror)
inc=(-I"$repo/contracts/qwen35" -I"$repo/modules/linear_A/xrt" -I/home/member-a/qwen35-a05/source-v3/vendor/nlohmann)
src=("$repo/platform/qwen35/a07/test_host.cpp" "$repo/modules/linear_A/xrt/host_contract.cpp")
set -x
g++ "${flags[@]}" "${inc[@]}" "${src[@]}" -o host-test
./host-test "$repo"
g++ "${flags[@]}" -fsanitize=address,undefined -fno-omit-frame-pointer "${inc[@]}" "${src[@]}" -o host-test-sanitized
ASAN_OPTIONS=detect_leaks=1 ./host-test-sanitized "$repo"
set +x
set +u
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
read -r -a compiler <<< "$CXX"
set -x
"${compiler[@]}" -mcpu=cortex-a53 "${flags[@]}" "${inc[@]}" "${src[@]}" -o host-test-a53
"${compiler[@]}" -mcpu=cortex-a53 -std=c++17 -O3 -fno-fast-math -ffp-contract=off -Wall -Wextra -fPIC -shared \
  "${inc[@]}" -I/home/member-a/qwen35-a05/source-v3/vendor/nlohmann \
  "$repo/modules/linear_A/xrt/backend.cpp" "$repo/modules/linear_A/xrt/host_contract.cpp" \
  -o libsp_linear_xrt_candidate.so -lxrt_coreutil -luuid -lcrypto -pthread -Wl,-z,defs
"$READELF" -h -d libsp_linear_xrt_candidate.so
"$NM" -D --defined-only libsp_linear_xrt_candidate.so
file host-test-a53
sha256sum host-test host-test-a53 libsp_linear_xrt_candidate.so
