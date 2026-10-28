#!/bin/bash
set -eo pipefail
source /home/member-a/AMDDesignTools/2026.1/Vitis/settings64.sh
set -u
test "$(tr -d ':\n' </sys/class/net/eth0/address)" = '00155dbc29e7'
python3 /mnt/c/Patientqwen/platform/qwen35/a06/retry_current_20261004.py
