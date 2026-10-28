#!/usr/bin/env bash
# New queue workspace only. Compile/link, never executes an ARM or XRT device operation.
set -eo pipefail
repo=/mnt/c/Patientqwen
sdk=/home/member-a/kv260-sdk-2026.1-common
source "$sdk/environment-setup-cortexa72-cortexa53-amd-linux"
set -u
test "$OECORE_SDK_VERSION" = 2026.1
test "$OECORE_TARGET_ARCH" = aarch64
test ! -e llama
python3 "$repo/platform/qwen35/a07/snapshot_build.py" "$PWD"
src=/home/member-a/qwen35-a05/source-v3
export CC=aarch64-amd-linux-gcc
export CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS"
export CPPFLAGS=""
tc="$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake"
set -x
"$CXX" --version
cmake -S "$src" -B "$PWD/llama" -DCMAKE_TOOLCHAIN_FILE="$tc" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON '-DCMAKE_INSTALL_RPATH=$ORIGIN' \
  -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8-a -DGGML_CPU_ALL_VARIANTS=OFF \
  -DGGML_CPU_KLEIDIAI=OFF -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DGGML_BLAS=OFF \
  -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=OFF -DGGML_RPC=OFF
cmake --build "$PWD/llama" --target llama -j 4
cmake -S "$repo/platform/qwen35/a07/cross" -B "$PWD/s1" \
  -DCMAKE_TOOLCHAIN_FILE="$tc" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DLLAMA_SOURCE="$src" -DLLAMA_BUILD="$PWD/llama"
cmake --build "$PWD/s1" -j 4
file "$PWD/s1/qwen35-s1" "$PWD/s1/libsp_linear_cpu.so"
"$READELF" -h -d -V "$PWD/s1/qwen35-s1"
sha256sum "$PWD/s1/qwen35-s1" "$PWD/s1/libsp_linear_cpu.so"
set +x
printf '%s\n' 'CROSS_BUILD_ONLY; ARM execution, speed, memory, BOARD: NOT_TESTED'
