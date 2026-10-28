#!/usr/bin/env bash
# PC only. Distinct kernel release, no deployment or changes to rejected build.
set -euo pipefail
source /mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/full_build_env.sh
old=/home/member-a/a10-kernel-full-20261019-v1
work=/home/member-a/a10-kernel-irq2-20261021-v1
for i in "${!build_args[@]}"; do
  build_args[$i]=${build_args[$i]//$old/$work}
done
umask 077
test "$(uname -m)" = x86_64
attempt=${1:-initial}
[[ "$attempt" =~ ^[a-z0-9_-]+$ ]]
log="$work/logs/build-$attempt.log"
if [[ "$attempt" = initial ]]; then log="$work/logs/build.log"; fi
test ! -e "$log"
exec 9>"$work/irq2-build.lock"
flock -n 9
test "$(sha256sum "$work/source/drivers/irqchip/irq-xilinx-intc.c" | cut -d ' ' -f1)" = 3e9b896dc046f2bbfa2208ff78f7fc0c136a98318e45f0cfe4ff90fcca8a4a07
"$work/source/scripts/config" --file "$work/build/.config" --set-str LOCALVERSION '-a10irq2' \
  --set-str VERSION_SIGNATURE 'A10 irq2 independent candidate; ownership fix; NOT_BOARD_ACCEPTED'
make "${build_args[@]}" olddefconfig
make "${build_args[@]}" prepare
test "$(make -s "${build_args[@]}" kernelrelease)" = 6.8.12-a10irq2
sha256sum "$work/build/.config"
set -o noclobber
set +e
nice -n 10 make "${build_args[@]}" -j8 Image modules dtbs >"$log" 2>&1
result=$?
set -e
tail -n 35 "$log"
printf 'IRQ2_PC_BUILD_EXIT=%s\n' "$result"
test "$result" = 0 || exit "$result"
sha256sum "$work/build/arch/arm64/boot/Image" "$work/build/Module.symvers" "$work/build/System.map"
printf 'PC_FULL_KERNEL_ONLY_NOT_BOARD_NOT_DEPLOYED\n'
