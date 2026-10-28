#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
evidence=$repo/evidence/model_pl_A/20261024-ttft10-01-v1
work=/home/member-a/kv260-build/a12-tt10-01-20261024-v1
test ! -e "$work"
mkdir -p "$work/source" "$work/cmake"
cp "$evidence/source/"* "$work/source/"
cp "$repo/platform/qwen35/a12/cpu01_CMakeLists.txt" "$work/cmake/CMakeLists.txt"
prior=$(python3 -c 'import json;print(json.load(open("/mnt/c/Patientqwen/evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json"))["workspace"])')
prior2=$(python3 -c 'import json;print(json.load(open("/mnt/c/Patientqwen/evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json"))["workspace"])')
cmake -S "$work/cmake" -B "$work/pc" -DCMAKE_BUILD_TYPE=Release -DROOT="$repo" -DA12_SOURCE="$work/source" -DASSET_ROOT="$repo" -DLLAMA_SOURCE="$prior/llama-source" -DLLAMA_BUILD="$prior/pc-llama" -DBASE_BUILD="$prior2/pc"
cmake --build "$work/pc" -j4
echo TT10_01_PC_BUILD_PASS
