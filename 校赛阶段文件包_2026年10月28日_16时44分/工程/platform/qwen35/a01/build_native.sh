#!/usr/bin/env bash
set -euo pipefail
cmake -S /mnt/c/Patientqwen/runtime/qwen35_cpu -B /home/member-a/qwen35-a01/native-build -DLLAMA_SOURCE=/home/member-a/qwen35-a01/llama.cpp-81e39ad34368329b5db77620721510fd91107e80 -DLLAMA_BUILD=/home/member-a/qwen35-a01/build-cpu -DCMAKE_BUILD_TYPE=Release
cmake --build /home/member-a/qwen35-a01/native-build -j 4
