#!/bin/bash
# Local WSL build only; no install, board connection, or package upgrades.
set -euo pipefail
cd /home/member-a/a13-fast-preboard-20261026-v1/build-01
kernel=/home/member-a/a13-muted-headers1036-20261025-v1/build-01/headers/linux-headers-6.8.0-1036-xilinx
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS
export PATH=/usr/bin:$PATH
make -C "$kernel" M="$PWD/bus" ARCH=arm64 CROSS_COMPILE=aarch64-amd-linux- CC=aarch64-amd-linux-gcc HOSTCC=/usr/bin/gcc W=1 -j2 modules
aarch64-amd-linux-gcc --sysroot="$SDKTARGETSYSROOT" -mcpu=cortex-a53 -O2 -Wall -Wextra -Werror pcm_zero_test.c -lasound -o pcm_zero_test
aarch64-amd-linux-readelf -h pcm_zero_test
aarch64-amd-linux-readelf -d pcm_zero_test
