#!/bin/bash
set -eo pipefail
source /home/member-a/AMDDesignTools/2026.1/Vitis/settings64.sh
set -u
export XILINXD_LICENSE_FILE=/home/member-a/.Xilinx/kv260-a-rehost-20261003.lic
python3 /mnt/c/Patientqwen/platform/qwen35/a06/test_supplement.py
