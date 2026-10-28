#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
work=/home/member-a/kv260-build/a12-tt10-01-20261024-v1
prior=$(python3 -c 'import json;print(json.load(open("/mnt/c/Patientqwen/evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json"))["workspace"])')
g++ -std=c++17 -O2 -DSP_A12_PC_TEST=1 "$repo/platform/qwen35/a12/tt10_01_store_test.cpp" -I"$work/source-02" -I"$prior/llama-source/vendor/nlohmann" -l:libcrypto.so.3 -o "$work/prefix_store_test"
"$work/prefix_store_test"
