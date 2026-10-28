#!/bin/bash
set -eo pipefail
source /home/member-a/AMDDesignTools/2026.1/Vitis/settings64.sh
set -u
export XILINXD_LICENSE_FILE=/home/member-a/.Xilinx/kv260-a-rehost-20261003.lic
test "$(sha256sum "$XILINXD_LICENSE_FILE" | cut -d ' ' -f 1)" = '46ef2a17d5100e55d7181a8e9b7acc4d79580852a921cdea6c5eeccb33bf177f'
test "$(tr -d ':\n' </sys/class/net/eth0/address)" = '00155dbc2453'
python3 /mnt/c/Patientqwen/platform/qwen35/a06/retry_csim_rehost.py
