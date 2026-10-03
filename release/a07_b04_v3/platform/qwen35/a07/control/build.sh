#!/usr/bin/env bash
set -euo pipefail
repo=/mnt/c/Patientqwen
python3 "$repo/platform/qwen35/a07/b04/prepare.py" "$PWD/inputs"
python3 "$repo/platform/qwen35/a07/control/snapshot.py" "$PWD/inputs"
root="$PWD/inputs"
testsrc="$root/platform/qwen35/a07/control"
inc=(-I"$root/contracts/qwen35" -I"$root/modules/linear_A/xrt" -I"$root/third_party/nlohmann")
flags=(-std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror)
pcssl=/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root
test -f "$pcssl/usr/include/openssl/evp.h"
pcdeps=(-I"$pcssl/usr/include" -I"$pcssl/usr/include/x86_64-linux-gnu" -L"$pcssl/usr/lib/x86_64-linux-gnu" -Wl,-rpath,"$pcssl/usr/lib/x86_64-linux-gnu")
src=("$testsrc/test_api.cpp" "$root/modules/linear_A/xrt/backend.cpp" "$root/modules/linear_A/xrt/host_contract.cpp")
set -x
g++ "${flags[@]}" -DSP_LINEAR_CONTROL_TEST=1 -I"$testsrc/stubs" "${inc[@]}" "${pcdeps[@]}" "${src[@]}" -lcrypto -pthread -o control-test
python3 "$testsrc/run_cases.py" "$PWD/control-test" "$PWD/control-normal"
g++ "${flags[@]}" -DSP_LINEAR_CONTROL_TEST=1 -I"$testsrc/stubs" "${inc[@]}" "${pcdeps[@]}" \
 -fsanitize=address,undefined -fno-omit-frame-pointer -no-pie "${src[@]}" -lcrypto -pthread -o control-test-sanitized
ASAN_OPTIONS=detect_leaks=1 python3 "$testsrc/run_cases.py" "$PWD/control-test-sanitized" "$PWD/control-sanitized"
set +x
# Real SDK production build: no control define and no stub headers in include paths.
set +u
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
read -r -a compiler <<< "$CXX"
set -x
"${compiler[@]}" -mcpu=cortex-a53 -std=c++17 -O3 -fno-fast-math -ffp-contract=off -Wall -Wextra -fPIC -shared \
 "${inc[@]}" "$root/modules/linear_A/xrt/backend.cpp" "$root/modules/linear_A/xrt/host_contract.cpp" \
 -o libsp_linear_xrt_candidate.so -lxrt_coreutil -luuid -lcrypto -pthread -Wl,-z,defs
"${compiler[@]}" -mcpu=cortex-a53 "${flags[@]}" "${inc[@]}" "$root/modules/linear_A/xrt/host.cpp" \
 -L. -lsp_linear_xrt_candidate -Wl,-rpath,'$ORIGIN' -o sp-linear-host
"$READELF" -h -d --dyn-syms --wide libsp_linear_xrt_candidate.so
"$READELF" -h -d --wide sp-linear-host
sha256sum libsp_linear_xrt_candidate.so sp-linear-host control-test control-test-sanitized
