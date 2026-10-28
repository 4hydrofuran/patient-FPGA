#!/usr/bin/env bash
# Computer-only execution of stub functions, never the ARM64 driver module.
set -euo pipefail
test "$(uname -m)" = x86_64
repo=/mnt/c/Patientqwen
src="$repo/platform/qwen35/a10/kernel_repair"
bundle="$repo/platform/build/a10-driver-irq-repair-20261019-v1"
out=/home/member-a/a10-driver-irq-tests-20261019-v2
python3 "$src/generate_driver_harness.py" --bundle "$bundle" --output "$out"
for kind in original candidate; do
  flags=()
  if [ "$kind" = original ]; then flags=(-DORIGINAL); fi
  for area in irq cu; do
    for mode in normal sanitized; do
      san=()
      if [ "$mode" = sanitized ]; then san=(-fsanitize=address,undefined -fno-omit-frame-pointer -no-pie); fi
      binary="$out/$kind/$area-$mode"
      /usr/bin/gcc -std=gnu11 -g -O1 -Wall -Wextra -Werror -Wno-sign-compare \
        "${flags[@]}" "${san[@]}" -I"$out/$kind" "$src/driver_${area}_harness.c" -o "$binary"
      timeout 10s "$binary"
      sha256sum "$binary"
    done
  done
done
printf 'PC_STUB_TESTS_ONLY_NO_BOARD_NO_HARDWARE_CONCURRENCY_PROOF\n'
