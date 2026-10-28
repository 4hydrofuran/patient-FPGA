#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
work=/home/member-a/kv260-build/a12-tt10-01-20261024-v1
mkdir "$work/source-03"
cp "$repo/evidence/model_pl_A/20261024-ttft10-01-v1/source-03/"* "$work/source-03/"
cmake -S "$work/cmake" -B "$work/pc" -DA12_SOURCE="$work/source-03"
cmake --build "$work/pc" -j4
echo TT10_01_PC03_BUILD_PASS
