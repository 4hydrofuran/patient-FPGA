#!/bin/bash
set -eo pipefail
if [ "$#" -ne 2 ]; then
    printf 'Usage: closeout_linux.sh UNIQUE_LABEL OFFICIAL_LICENSE_PATH\n' >&2
    exit 2
fi
source /home/member-a/AMDDesignTools/2026.1/Vitis/settings64.sh
set -u
python3 /mnt/c/Patientqwen/platform/qwen35/a06/closeout_csim.py \
  --work "$PWD/current-source-csim" --label "$1" --license "$2"
