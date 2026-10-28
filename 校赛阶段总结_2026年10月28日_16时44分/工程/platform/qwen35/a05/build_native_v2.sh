#!/usr/bin/env bash
set -euo pipefail
cmake -S /mnt/c/Patientqwen/runtime/qwen35_w4a8 -B /home/member-a/qwen35-a05/build-v2 -DCMAKE_BUILD_TYPE=Release
cmake --build /home/member-a/qwen35-a05/build-v2 -j 4
