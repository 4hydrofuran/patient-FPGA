#!/usr/bin/env bash
# PC-only inventory of the verified backup. No boot, execution or extraction.
set -euo pipefail
test "$(uname -m)" = x86_64
work=/home/member-a/a10-kernel-full-20261019-v1
input="$work/original-boot-v2/ramdisk"
output="$work/original-boot-v2/initramfs-files.txt"
test "$(sha256sum "$input" | cut -d ' ' -f1)" = cdfd3b01230944d912f66475b38283bfdb576f516cbb38fd0da4077354b48a94
export LD_LIBRARY_PATH="$work/deps/root/usr/lib/x86_64-linux-gnu"
export PATH="$work/deps/root/usr/bin:$work/deps/root/usr/sbin:/usr/bin:/bin"
set -o noclobber
timeout 30s lsinitramfs "$input" > "$output"
sha256sum "$output"
printf 'FILE_ENTRIES='
wc -l < "$output"
printf 'MODULE_DIRECTORIES\n'
grep -E '^(usr/)?lib/modules/[^/]+$' "$output"
printf 'ROOT_BOOT_SUPPORT_PATHS\n'
grep -E '/(sdhci[^/]*|mmc[^/]*|ext4|jbd2|mbcache|phy-zynqmp|reset-zynqmp)\.ko([.].*)?$|^init$|/scripts/local$|/scripts/local-premount/|/modules\.(dep|alias|builtin)$' "$output"
printf 'ORIGINAL_INITRAMFS_INVENTORY_ONLY_NOT_CANDIDATE_COMPATIBILITY\n'
