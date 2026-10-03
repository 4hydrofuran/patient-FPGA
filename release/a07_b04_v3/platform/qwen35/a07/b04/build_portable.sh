#!/usr/bin/env bash
# Usage from a NEW build directory: bash build_portable.sh ROOT JSON_INCLUDE SDK_ENV
set -euo pipefail
root=$(realpath "$1")
json_include=$(realpath "$2")
sdk_env=$(realpath "$3")
test ! -e host-test
flags=(-std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror)
inc=(-I"$root/contracts/qwen35" -I"$root/modules/linear_A/xrt" -I"$json_include")
logic="$root/modules/linear_A/xrt/host_contract.cpp"
tests="$root/platform/qwen35/a07"
fixtures="$root/hw/linear_B_received/B04-scope-9a75600-20261003/vectors/b04_meta"
set -x
g++ "${flags[@]}" "${inc[@]}" "$tests/test_host.cpp" "$logic" -o host-test
./host-test "$root"
g++ "${flags[@]}" -fsanitize=address,undefined -fno-omit-frame-pointer "${inc[@]}" "$tests/test_host.cpp" "$logic" -o host-test-sanitized
ASAN_OPTIONS=detect_leaks=1 ./host-test-sanitized "$root"
g++ "${flags[@]}" "${inc[@]}" "$tests/b04/meta_replay.cpp" "$logic" -o meta-replay
./meta-replay "$fixtures"
g++ "${flags[@]}" -fsanitize=address,undefined -fno-omit-frame-pointer "${inc[@]}" "$tests/b04/meta_replay.cpp" "$logic" -o meta-replay-sanitized
ASAN_OPTIONS=detect_leaks=1 ./meta-replay-sanitized "$fixtures"
set +x
set +u
source "$sdk_env"
set -u
read -r -a compiler <<< "$CXX"
set -x
"${compiler[@]}" -mcpu=cortex-a53 -std=c++17 -O3 -fno-fast-math -ffp-contract=off -Wall -Wextra -fPIC -shared \
  "${inc[@]}" "$root/modules/linear_A/xrt/backend.cpp" "$logic" \
  -o libsp_linear_xrt_candidate.so -lxrt_coreutil -luuid -lcrypto -pthread -Wl,-z,defs
"${compiler[@]}" -mcpu=cortex-a53 "${flags[@]}" "${inc[@]}" "$root/modules/linear_A/xrt/host.cpp" \
  -L. -lsp_linear_xrt_candidate -Wl,-rpath,'$ORIGIN' -o sp-linear-host
"$READELF" --file-header --dynamic --dyn-syms --wide libsp_linear_xrt_candidate.so
"$READELF" --file-header --dynamic --wide sp-linear-host
sha256sum host-test meta-replay libsp_linear_xrt_candidate.so sp-linear-host
