#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
evidence=$repo/evidence/model_pl_A/20261024-step10-v1
python3 -B "$repo/platform/qwen35/a12/step10_llama_derive.py"
src=$PWD/llama-source
cmake -S "$src" -B "$PWD/pc-llama" -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF \
 -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=OFF -DLLAMA_BUILD_SERVER=OFF -DLLAMA_CURL=OFF
cmake --build "$PWD/pc-llama" --target llama ggml -j4
cmake -S "$repo/platform/qwen35/a12" -B "$PWD/pc" -DCMAKE_BUILD_TYPE=Release \
 -DA12_SOURCE="$evidence/source-v1" -DLLAMA_SOURCE="$src" -DLLAMA_BUILD="$PWD/pc-llama"
cmake --build "$PWD/pc" -j4
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
test "$OECORE_SDK_VERSION" = 2026.1
export CC=aarch64-amd-linux-gcc
export CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS"
export CPPFLAGS=""
tc=$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake
cmake -S "$src" -B "$PWD/arm-llama" -DCMAKE_TOOLCHAIN_FILE="$tc" -DCMAKE_BUILD_TYPE=Release \
 -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8-a -DGGML_OPENMP=ON \
 -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=OFF -DLLAMA_BUILD_SERVER=OFF -DLLAMA_CURL=OFF
cmake --build "$PWD/arm-llama" --target llama ggml -j4
cmake -S "$repo/platform/qwen35/a12" -B "$PWD/model" -DCMAKE_TOOLCHAIN_FILE="$tc" -DCMAKE_BUILD_TYPE=Release \
 -DA12_SOURCE="$evidence/source-v1" -DASSET_ROOT=/opt/patient-qwen -DLLAMA_SOURCE="$src" -DLLAMA_BUILD="$PWD/arm-llama"
cmake --build "$PWD/model" -j4
xrt218=/home/member-a/a10-driver-audit-20261018/xrt-userspace/usr
read -r -a compiler <<< "$CXX"
"${compiler[@]}" $CXXFLAGS -std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror -fPIC -shared \
 -I"$xrt218/include/xrt" -I"$repo/contracts/qwen35" -I"$repo/modules/linear_A/xrt" \
 -I"$repo/release/a07_b04_v3/third_party/nlohmann" -I"$repo/platform/qwen35/a11" \
 -I"$evidence/source-v1" "$evidence/source-v1/backend.cpp" "$repo/modules/linear_A/xrt/host_contract.cpp" \
 "$xrt218/lib/libxrt_coreutil.so.2.18.0" -luuid -lcrypto -pthread -Wl,-z,defs -Wl,-Bsymbolic-functions \
 -Wl,--version-script="$evidence/source-v1/sp_abi.map" -Wl,-soname,libsp_linear_a12_trial.so \
 -o "$PWD/libsp_linear_a12_trial.so"
python3 -B "$repo/platform/qwen35/a12/step10_build_audit.py"
