#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS
set -u
export LD_LIBRARY_PATH=/home/member-a/a10-kernel-full-20261019-v1/deps/root/usr/lib/x86_64-linux-gnu
exec 9>/home/member-a/a10-kernel-irq2-20261021-v1/irq2-build.lock
flock -n 9
python3 /mnt/c/Patientqwen/platform/qwen35/a13/audio_signoff/prepare_locked.py
make -C /home/member-a/a10-kernel-irq2-20261021-v1/build ARCH=arm64 CROSS_COMPILE=aarch64-amd-linux- CC=aarch64-amd-linux-gcc PAHOLE=/home/member-a/a10-kernel-full-20261019-v1/deps/root/usr/bin/pahole M="$PWD/modules" -j2 modules
aarch64-amd-linux-readelf -h modules/a13_wm8960_card.ko modules/a13_formatter_pcm.ko
modinfo modules/a13_wm8960_card.ko
modinfo modules/a13_formatter_pcm.ko
