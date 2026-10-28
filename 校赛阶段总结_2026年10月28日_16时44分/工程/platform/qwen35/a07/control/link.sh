#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
source /home/member-a/AMDDesignTools/2026.1/Vitis/settings64.sh
export XILINXD_LICENSE_FILE=/home/member-a/.Xilinx/kv260-a-rehost-20261004-29e7.lic
unset LM_LICENSE_FILE XCL_EMULATION_MODE
set -u
mkdir inputs
cp "$repo/platform/qwen35/a07/b04/link_offline.py" "$repo/platform/qwen35/a07/b04/link.cfg" inputs/
cp "$repo/hw/linear_A/KERNEL_SOURCE.json" inputs/KERNEL_SOURCE.json
sha256sum inputs/*
python3 inputs/link_offline.py --root "$repo" \
 --platform /home/member-a/AMDDesignTools/2026.1/Vitis/base_platforms/kv260_base/kv260_base.xpfm \
 --xo "$repo/hw/linear_B_received/B03-supplement-e227297-20261003/payload/artifact/b03_candidate/w4a8_linear_v1.xo"
