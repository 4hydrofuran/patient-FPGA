#!/usr/bin/env bash
# PC-only native and sanitizer checks of extracted real function bodies.
set -euo pipefail
test "$(uname -m)" = x86_64
repo=/mnt/c/Patientqwen
out=/home/member-a/a10-kernel-repair-native-20261019-v4
test ! -e "$out"
python3 "$repo/platform/qwen35/a10/kernel_repair/generate_harness.py" \
  --bundle "$repo/platform/build/a10-kernel-repair-20261019-v2" --output "$out"
for kind in original candidate; do
  fixed=0
  if test "$kind" = candidate; then fixed=1; fi
  # Linux uses -Wno-sign-compare; retain original kernel int/u32 loop types.
  gcc -std=gnu11 -O1 -g -Wall -Wextra -Werror -Wno-sign-compare -DFIXED="$fixed" -I"$out/$kind" \
    "$repo/platform/qwen35/a10/kernel_repair/harness.c" -o "$out/$kind/check"
  "$out/$kind/check"
  gcc -std=gnu11 -O1 -g -Wall -Wextra -Werror -Wno-sign-compare -DFIXED="$fixed" -I"$out/$kind" \
    -fsanitize=address,undefined -fno-omit-frame-pointer \
    "$repo/platform/qwen35/a10/kernel_repair/harness.c" -o "$out/$kind/check-san"
  "$out/$kind/check-san"
  gcc -std=gnu11 -O1 -g -Wall -Wextra -Werror -Wno-sign-compare -DFIXED="$fixed" -I"$out/$kind" \
    "$repo/platform/qwen35/a10/kernel_repair/parent_harness.c" -o "$out/$kind/parent-check"
  "$out/$kind/parent-check"
  gcc -std=gnu11 -O1 -g -Wall -Wextra -Werror -Wno-sign-compare -DFIXED="$fixed" -I"$out/$kind" \
    -fsanitize=address,undefined -fno-omit-frame-pointer \
    "$repo/platform/qwen35/a10/kernel_repair/parent_harness.c" -o "$out/$kind/parent-check-san"
  "$out/$kind/parent-check-san"
done
