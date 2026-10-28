#!/usr/bin/env bash
set -euo pipefail
repo=/mnt/c/Patientqwen
work=$1
test ! -e "$work"
mkdir -p "$work"
g++ -std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror -fPIC -shared \
  -I"$repo/quant/reference" "$repo/platform/qwen35/a11/quant_adapter.cpp" \
  "$repo/quant/reference/w4a8.cpp" -o "$work/liba11_quant_PC_ONLY.so"
python3 -B "$repo/platform/qwen35/a11/test_engine.py" --quant "$work/liba11_quant_PC_ONLY.so"
set +u
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
read -r -a compiler <<< "$CXX"
"${compiler[@]}" -mcpu=cortex-a53 -std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror -fPIC -shared \
  -I"$repo/quant/reference" "$repo/platform/qwen35/a11/quant_adapter.cpp" \
  "$repo/quant/reference/w4a8.cpp" -Wl,-z,defs -o "$work/liba11_quant.so"
"$READELF" -h -d -V --wide "$work/liba11_quant.so"
sha256sum "$work/liba11_quant.so"
