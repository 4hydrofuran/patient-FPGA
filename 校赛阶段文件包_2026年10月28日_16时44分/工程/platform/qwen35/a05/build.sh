#!/usr/bin/env bash
set -euo pipefail
src=/home/member-a/qwen35-a05/source-v1
lib=/home/member-a/qwen35-a05/llama-build-v1
cmake -S "$src" -B "$lib" -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DGGML_BLAS=OFF -DGGML_NATIVE=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF -DLLAMA_BUILD_EXAMPLES=OFF
cmake --build "$lib" --target llama -j 4
cmake -S /mnt/c/Patientqwen/runtime/qwen35_w4a8 -B /home/member-a/qwen35-a05/build-v1 -DCMAKE_BUILD_TYPE=Release
cmake --build /home/member-a/qwen35-a05/build-v1 -j 4
