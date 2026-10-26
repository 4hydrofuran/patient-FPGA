#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
evidence=$repo/evidence/model_pl_A/20261024-ttft10-01-v1
work=/home/member-a/kv260-build/a12-tt10-01-20261024-v1
test -f "$evidence/PC_DIAGNOSTIC_04.json"
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
test "$OECORE_SDK_VERSION" = 2026.1
export CC=aarch64-amd-linux-gcc CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS" CPPFLAGS=""
prior=$(python3 -c 'import json;print(json.load(open("/mnt/c/Patientqwen/evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json"))["workspace"])')
prior2=$(python3 -c 'import json;print(json.load(open("/mnt/c/Patientqwen/evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json"))["workspace"])')
cmake -S "$work/cmake" -B "$work/arm04" -DCMAKE_TOOLCHAIN_FILE="$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake" -DCMAKE_BUILD_TYPE=Release -DROOT="$repo" -DA12_SOURCE="$work/source-04" -DASSET_ROOT=/opt/patient-qwen -DLLAMA_SOURCE="$prior/llama-source" -DLLAMA_BUILD="$prior/arm-llama" -DBASE_BUILD="$prior2/model"
cmake --build "$work/arm04" -j4
mkdir "$evidence/build-arm04"
cp "$work/arm04/qwen35-a12" "$evidence/build-arm04/qwen35-a12"
readelf -h -d -Ws "$work/arm04/qwen35-a12" > "$evidence/build-arm04/arm-elf.txt"
cp "$work/arm04/CMakeCache.txt" "$work/arm04/CMakeFiles/qwen35-a12.dir/flags.make" "$work/arm04/CMakeFiles/qwen35-a12.dir/link.txt" "$evidence/build-arm04/"
echo TT10_01_A53_04_BUILD_PASS
