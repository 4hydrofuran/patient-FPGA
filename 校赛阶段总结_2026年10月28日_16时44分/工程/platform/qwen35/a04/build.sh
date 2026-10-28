#!/usr/bin/env bash
set -euo pipefail
root=/mnt/c/Patientqwen
out=/home/member-a/qwen35-a04/build-v1
mkdir -p "$out"
g++ --version
g++ -std=c++17 -O3 -fno-fast-math -ffp-contract=off -Wall -Wextra \
    -fopt-info-vec-optimized="$out/vectorization.txt" \
    "$root/quant/reference/w4a8.cpp" "$root/quant/reference/main.cpp" -o "$out/w4ref"
g++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
    -fno-fast-math -ffp-contract=off \
    "$root/quant/reference/w4a8.cpp" "$root/quant/reference/main.cpp" -o "$out/w4ref-sanitize"
sha256sum "$out/w4ref" "$out/w4ref-sanitize"
