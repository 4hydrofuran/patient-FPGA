#!/bin/bash
# 仅交叉构建新离线模块，必须在协作队列中运行；不部署、不访问板卡。
set -euo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS
export LD_LIBRARY_PATH=/home/member-a/a10-kernel-full-20261019-v1/deps/root/usr/lib/x86_64-linux-gnu
exec 9>/home/member-a/a10-kernel-irq2-20261021-v1/irq2-build.lock
flock -n 9
python3 /mnt/c/Patientqwen/platform/qwen35/a13/codec_master/prepare_dma.py
make -C /home/member-a/a10-kernel-irq2-20261021-v1/build ARCH=arm64 CROSS_COMPILE=aarch64-amd-linux- CC=aarch64-amd-linux-gcc PAHOLE=/home/member-a/a10-kernel-full-20261019-v1/deps/root/usr/bin/pahole M="$PWD/modules" -j2 modules
for candidate in modules/*.ko; do
    aarch64-amd-linux-readelf -h "$candidate"
    modinfo "$candidate"
done
