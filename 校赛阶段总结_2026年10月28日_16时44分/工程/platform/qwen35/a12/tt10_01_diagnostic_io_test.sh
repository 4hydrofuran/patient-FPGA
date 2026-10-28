#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
work=/home/member-a/kv260-build/a12-tt10-01-20261024-v1
g++ -std=c++17 -O2 -I "$repo/runtime/qwen35_w4a8/a12/tt10_01" "$repo/platform/qwen35/a12/tt10_01_diagnostic_io_test.cpp" -o "$work/diagnostic-io-test"
"$work/diagnostic-io-test" "$work/diagnostic-io-test-files"
