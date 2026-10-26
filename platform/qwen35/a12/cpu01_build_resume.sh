#!/usr/bin/env bash
# First build's missing unversioned host crypto linker name is retained in build_01.
set -eo pipefail
repo=/mnt/c/Patientqwen
evidence=$repo/evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1
work=/home/member-a/kv260-build/a12-cpu01-integrated-20261024-v1
cp "$repo/platform/qwen35/a12/cpu01_CMakeLists.txt" "$work/cmake/CMakeLists.txt"
prior=$(python3 -c 'import json;print(json.load(open("/mnt/c/Patientqwen/evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json"))["workspace"])')
prior2=$(python3 -c 'import json;print(json.load(open("/mnt/c/Patientqwen/evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json"))["workspace"])')
cmake -S "$work/cmake" -B "$work/pc" -DCMAKE_BUILD_TYPE=Release -DROOT="$repo" -DA12_SOURCE="$work/source" -DASSET_ROOT="$repo" -DLLAMA_SOURCE="$prior/llama-source" -DLLAMA_BUILD="$prior/pc-llama" -DBASE_BUILD="$prior2/pc"
cmake --build "$work/pc" -j4
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
test "$OECORE_SDK_VERSION" = 2026.1
export CC=aarch64-amd-linux-gcc CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS" CPPFLAGS=""
cmake -S "$work/cmake" -B "$work/arm" -DCMAKE_TOOLCHAIN_FILE="$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake" -DCMAKE_BUILD_TYPE=Release -DROOT="$repo" -DA12_SOURCE="$work/source" -DASSET_ROOT=/opt/patient-qwen -DLLAMA_SOURCE="$prior/llama-source" -DLLAMA_BUILD="$prior/arm-llama" -DBASE_BUILD="$prior2/model"
cmake --build "$work/arm" -j4
mkdir "$evidence/build"
cp "$work/arm/qwen35-a12" "$evidence/build/qwen35-a12"
readelf -h -d -Ws "$work/arm/qwen35-a12" > "$evidence/build/arm-elf.txt"
cp "$work/arm/CMakeCache.txt" "$work/arm/CMakeFiles/qwen35-a12.dir/flags.make" "$work/arm/CMakeFiles/qwen35-a12.dir/link.txt" "$evidence/build/"
echo CPU01_PC_COMPONENTS_PC_AND_A53_BUILD_PASS
