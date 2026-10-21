#!/usr/bin/env bash
# New empty build directory; ROOT PC_OPENSSL_PREFIX (use /usr for system libssl-dev).
set -euo pipefail
root=$(realpath "$1")
ssl=$(realpath "$2")
test ! -e control-test
inc=(-I"$root/contracts/qwen35" -I"$root/modules/linear_A/xrt" -I"$root/third_party/nlohmann")
testsrc="$root/platform/qwen35/a07/control"
flags=(-std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror -DSP_LINEAR_CONTROL_TEST=1)
sslflags=(-I"$ssl/include" -I"$ssl/include/x86_64-linux-gnu" -L"$ssl/lib/x86_64-linux-gnu" -Wl,-rpath,"$ssl/lib/x86_64-linux-gnu")
src=("$testsrc/test_api.cpp" "$root/modules/linear_A/xrt/backend.cpp" "$root/modules/linear_A/xrt/host_contract.cpp")
set -x
g++ "${flags[@]}" -I"$testsrc/stubs" "${inc[@]}" "${sslflags[@]}" "${src[@]}" -lcrypto -pthread -o control-test
python3 "$testsrc/run_cases.py" "$PWD/control-test" "$PWD/control-normal"
g++ "${flags[@]}" -I"$testsrc/stubs" "${inc[@]}" "${sslflags[@]}" -fsanitize=address,undefined -fno-omit-frame-pointer -no-pie "${src[@]}" -lcrypto -pthread -o control-test-sanitized
ASAN_OPTIONS=detect_leaks=1 python3 "$testsrc/run_cases.py" "$PWD/control-test-sanitized" "$PWD/control-sanitized"
