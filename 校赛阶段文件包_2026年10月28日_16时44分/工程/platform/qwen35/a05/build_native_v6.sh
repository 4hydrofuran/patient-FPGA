#!/usr/bin/env bash
set -euo pipefail
cmake -S /mnt/c/Patientqwen/runtime/qwen35_w4a8 -B /home/member-a/qwen35-a05/build-v6 -DCMAKE_BUILD_TYPE=Release -DLLAMA_SOURCE=/home/member-a/qwen35-a05/source-v2 -DLLAMA_BUILD=/home/member-a/qwen35-a05/llama-build-v2
cmake --build /home/member-a/qwen35-a05/build-v6 -j 4
