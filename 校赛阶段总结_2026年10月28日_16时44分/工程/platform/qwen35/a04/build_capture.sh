#!/usr/bin/env bash
set -euo pipefail
root=/mnt/c/Patientqwen
src=/home/member-a/qwen35-a01/llama.cpp-81e39ad34368329b5db77620721510fd91107e80
lib=/home/member-a/qwen35-a01/build-cpu/bin
out=/home/member-a/qwen35-a04/build-v1
g++ -std=c++17 -O3 -fno-fast-math -ffp-contract=off -Wall -Wextra \
    -I"$src/include" -I"$src/ggml/include" -I"$src/vendor/nlohmann" \
    "$root/platform/qwen35/a04/capture.cpp" -L"$lib" -Wl,-rpath,"$lib" \
    -lllama -lggml-base -o "$out/capture"
sha256sum "$out/capture"
