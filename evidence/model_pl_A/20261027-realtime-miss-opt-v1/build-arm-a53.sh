#!/usr/bin/env bash
set -euo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
exec python3 -B platform/qwen35/a12/realtime_draft_derive.py --build ARM --revision v3 --arm-a53
