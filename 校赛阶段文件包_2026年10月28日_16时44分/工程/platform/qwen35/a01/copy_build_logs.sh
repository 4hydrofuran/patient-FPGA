#!/usr/bin/env bash
set -euo pipefail
out=/mnt/c/Patientqwen/eval/qwen35/a01/build
mkdir "$out"
base=/home/member-a/kv260-build/ra02-coordinator/work
cp "$base/01790873987954784178-A-qwen35-cpu-b8e5141b/stdout.txt" "$out/llama-stdout.txt"
cp "$base/01790873987954784178-A-qwen35-cpu-b8e5141b/stderr.txt" "$out/llama-stderr.txt"
cp "$base/01790874374418568029-A-qwen35-native-6410479b/stdout.txt" "$out/native-stdout.txt"
cp "$base/01790874374418568029-A-qwen35-native-6410479b/stderr.txt" "$out/native-stderr.txt"
cp /home/member-a/qwen35-a01/build-cpu/CMakeCache.txt "$out/llama-CMakeCache.txt"
cp /home/member-a/qwen35-a01/native-build/CMakeCache.txt "$out/native-CMakeCache.txt"
