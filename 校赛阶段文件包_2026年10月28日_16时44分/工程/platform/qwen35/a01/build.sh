#!/usr/bin/env bash
set -euo pipefail
src=/home/member-a/qwen35-a01/llama.cpp-81e39ad34368329b5db77620721510fd91107e80
build=/home/member-a/qwen35-a01/build-cpu
cmake -S "$src" -B "$build" -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DGGML_BLAS=OFF -DGGML_NATIVE=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=ON
cmake --build "$build" --target llama-server llama-cli llama-quantize -j 4
"$build/bin/llama-server" --version
"$build/bin/llama-server" --help
