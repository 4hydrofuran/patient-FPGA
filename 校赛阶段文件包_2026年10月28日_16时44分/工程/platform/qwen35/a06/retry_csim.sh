#!/bin/bash
set -eo pipefail
source /home/member-a/AMDDesignTools/2026.1/Vitis/settings64.sh
set -u
python3 /mnt/c/Patientqwen/platform/qwen35/a06/retry_csim.py "$@"
