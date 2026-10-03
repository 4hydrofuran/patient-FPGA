#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/AMDDesignTools/2026.1/Vitis/settings64.sh
export XILINXD_LICENSE_FILE=/home/member-a/.Xilinx/kv260-a-rehost-20261004-29e7.lic
unset LM_LICENSE_FILE XCL_EMULATION_MODE
set -u
python3 /mnt/c/Patientqwen/platform/qwen35/a07/control/audit_link.py "$1"
