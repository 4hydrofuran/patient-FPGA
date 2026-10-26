#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
evidence=$repo/evidence/model_pl_A/20261024-step10-v1
prior=$(python3 -c 'import json;print(json.load(open("/mnt/c/Patientqwen/evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json"))["workspace"])')
src=$prior/llama-source
cmake -S "$repo/platform/qwen35/a12" -B "$PWD/pc" -DCMAKE_BUILD_TYPE=Release \
 -DA12_SOURCE="$evidence/source-v2" -DLLAMA_SOURCE="$src" -DLLAMA_BUILD="$prior/pc-llama"
cmake --build "$PWD/pc" -j4
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
export CC=aarch64-amd-linux-gcc
export CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS"
export CPPFLAGS=""
tc=$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake
cmake -S "$repo/platform/qwen35/a12" -B "$PWD/model" -DCMAKE_TOOLCHAIN_FILE="$tc" -DCMAKE_BUILD_TYPE=Release \
 -DA12_SOURCE="$evidence/source-v2" -DASSET_ROOT=/opt/patient-qwen -DLLAMA_SOURCE="$src" -DLLAMA_BUILD="$prior/arm-llama"
cmake --build "$PWD/model" -j4
cp "$prior/libsp_linear_a12_trial.so" "$PWD/libsp_linear_a12_trial.so"
ln -s "$prior/arm-llama" "$PWD/arm-llama"
export A12_SOURCE_VERSION=2
python3 -B "$repo/platform/qwen35/a12/step10_build_audit.py"
