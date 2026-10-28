#!/usr/bin/env bash
set -euo pipefail
repo=/mnt/c/Patientqwen
python3 "$repo/platform/qwen35/a07/b04/prepare.py" "$PWD/inputs"
bash "$PWD/inputs/platform/qwen35/a07/b04/build_portable.sh" "$PWD/inputs" "$PWD/inputs/third_party/nlohmann" \
 /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
