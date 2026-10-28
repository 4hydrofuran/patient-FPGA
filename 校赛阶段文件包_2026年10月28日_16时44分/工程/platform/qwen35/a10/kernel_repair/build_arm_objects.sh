#!/usr/bin/env bash
# PC only; compile full translation units, never link/install a module/kernel.
set -euo pipefail
test "$(uname -m)" = x86_64
repo=/mnt/c/Patientqwen
out=/home/member-a/a10-kernel-repair-arm-20261019-v3
kernel=/home/member-a/a10-driver-audit-20261018/headers/usr/src/linux-headers-6.8.0-1015-xilinx
check_headers() {
  test "$(sha256sum "$kernel/.config" | cut -d ' ' -f1)" = 6ebb559a50a68b26bd0a681ea010264525af09cc4faa7814abfc0a1ddd20ff2e
  test "$(sha256sum "$kernel/Module.symvers" | cut -d ' ' -f1)" = 7e93bbb17224ef84a9641c4fca7481323adf5dca4b3f46329327707003a818b3
}
check_headers
python3 "$repo/platform/qwen35/a10/kernel_repair/prepare_arm_objects.py" \
  --bundle "$repo/platform/build/a10-kernel-repair-20261019-v2" \
  --archives "$repo/platform/local/a10-kernel-refaudit-20261019" --output "$out"
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS
timeout 120s make -C "$kernel" M="$out" -j2 ARCH=arm64 \
  CROSS_COMPILE=aarch64-amd-linux- CC=aarch64-amd-linux-gcc HOSTCC=/usr/bin/gcc \
  drivers/of/irq.o drivers/irqchip/irq-xilinx-intc.o drivers/irqchip/irqchip.o
file "$out/drivers/of/irq.o" "$out/drivers/irqchip/irq-xilinx-intc.o" "$out/drivers/irqchip/irqchip.o"
sha256sum "$out/drivers/of/irq.o" "$out/drivers/irqchip/irq-xilinx-intc.o" "$out/drivers/irqchip/irqchip.o"
check_headers
