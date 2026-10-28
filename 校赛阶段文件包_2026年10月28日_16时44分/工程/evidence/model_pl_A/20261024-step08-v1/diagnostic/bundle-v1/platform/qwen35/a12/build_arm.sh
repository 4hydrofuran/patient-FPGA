#!/usr/bin/env bash
# Existing 2026.1 SDK, fresh queue workspace. No board access or system install.
set -eo pipefail
repo=/mnt/c/Patientqwen
evidence=$repo/evidence/model_pl_A/20261023-preboard-v1
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
test "$OECORE_SDK_VERSION" = 2026.1
test "$OECORE_TARGET_ARCH" = aarch64
src=/home/member-a/qwen35-a05/source-v3
tc=$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake
export CC=aarch64-amd-linux-gcc
export CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS"
export CPPFLAGS=""
cmake -S "$src" -B "$PWD/llama" -DCMAKE_TOOLCHAIN_FILE="$tc" \
 -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
 -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON '-DCMAKE_INSTALL_RPATH=$ORIGIN' \
 -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8-a -DGGML_CPU_ALL_VARIANTS=OFF \
 -DGGML_CPU_KLEIDIAI=OFF -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DGGML_BLAS=OFF \
 -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF \
 -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=OFF -DGGML_RPC=OFF
cmake --build "$PWD/llama" --target llama -j4
cmake -S "$repo/platform/qwen35/a12" -B "$PWD/model" \
 -DCMAKE_TOOLCHAIN_FILE="$tc" -DCMAKE_BUILD_TYPE=Release \
 -DA12_SOURCE="$evidence/source-v3" -DASSET_ROOT=/opt/patient-qwen \
 -DLLAMA_SOURCE="$src" -DLLAMA_BUILD="$PWD/llama"
cmake --build "$PWD/model" -j4
xrt218=/home/member-a/a10-driver-audit-20261018/xrt-userspace/usr
read -r -a compiler <<< "$CXX"
"${compiler[@]}" $CXXFLAGS -std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror -fPIC -shared \
 -I"$xrt218/include/xrt" -I"$repo/contracts/qwen35" -I"$repo/modules/linear_A/xrt" \
 -I"$repo/release/a07_b04_v3/third_party/nlohmann" -I"$repo/platform/qwen35/a11" \
 -I"$evidence/source-v3" "$evidence/source-v3/backend.cpp" "$repo/modules/linear_A/xrt/host_contract.cpp" \
 "$xrt218/lib/libxrt_coreutil.so.2.18.0" -luuid -lcrypto -pthread -Wl,-z,defs -Wl,-Bsymbolic-functions \
 -Wl,--version-script="$evidence/source-v3/sp_abi.map" -Wl,-soname,libsp_linear_a12_trial.so \
 -o "$PWD/libsp_linear_a12_trial.so"
python3 -B "$repo/platform/qwen35/a12/audit_arm.py" "$PWD"
