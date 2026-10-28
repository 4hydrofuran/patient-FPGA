#!/usr/bin/env bash
set -euo pipefail
root=/mnt/c/Patientqwen
g++ -std=c++17 -O3 -fno-fast-math -ffp-contract=off -I "$root/quant/reference" -I "$root/runtime/qwen35_w4a8" "$root/platform/qwen35/a05/test_simd.cpp" "$root/quant/reference/w4a8.cpp" -o /home/member-a/qwen35-a05/test-simd-v1
/home/member-a/qwen35-a05/test-simd-v1
