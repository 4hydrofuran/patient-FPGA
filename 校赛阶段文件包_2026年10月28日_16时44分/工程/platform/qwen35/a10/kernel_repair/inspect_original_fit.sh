#!/usr/bin/env bash
# Read-only with respect to the board and original backup; extract locally only.
set -euo pipefail
test "$(uname -m)" = x86_64
work=/home/member-a/a10-kernel-full-20261019-v1
output="$work/original-boot-v2"
fit=/mnt/c/Patientqwen/platform/local/a10-boot-backup-20261019/fit-v2/image.fit
test "$(sha256sum "$fit" | cut -d ' ' -f1)" = b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9
# The first attempt's cached apt index referenced a removed .7 package (404).
# Keep that receipt and the four successful downloads. Refresh only private
# signed indexes, with no system apt update, package installation or upgrade.
mkdir "$work/deps/boot-apt-v2" "$work/deps/boot-downloads-v2" "$output"
mkdir -p "$work/deps/boot-apt-v2/lists/partial" "$work/deps/boot-apt-v2/cache/archives/partial"
apt_options=(-o "Dir::State::lists=$work/deps/boot-apt-v2/lists"
  -o "Dir::Cache=$work/deps/boot-apt-v2/cache"
  -o "Dir::Etc::sourcelist=/mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/host_boot_tools.sources"
  -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0
  -o Acquire::Languages=none)
timeout 120s apt-get "${apt_options[@]}" update
cd "$work/deps/boot-downloads-v2"
timeout 60s apt-get "${apt_options[@]}" download u-boot-tools
for package in "$work"/deps/boot-downloads/*.deb "$work"/deps/boot-downloads-v2/*.deb; do
  sha256sum "$package"
  dpkg-deb -x "$package" "$work/deps/root"
done
export LD_LIBRARY_PATH="$work/deps/root/usr/lib/x86_64-linux-gnu"
export PATH="$work/deps/root/usr/bin:$work/deps/root/usr/sbin:/usr/bin:/bin"
dumpimage -l "$fit"
dumpimage -T flat_dt -p 0 -o "$output/kernel.gz" "$fit"
dumpimage -T flat_dt -p 1 -o "$output/ramdisk" "$fit"
dumpimage -T flat_dt -p 6 -o "$output/kv260-revB.dtb" "$fit"
test "$(sha256sum "$output/kernel.gz" | cut -d ' ' -f1)" = b0b4434dc32f6d6662ff91d0b35b835fd2f523ee8c51d58c5651cde24d3092dc
file "$output/kernel.gz" "$output/ramdisk" "$output/kv260-revB.dtb"
sha256sum "$output/kernel.gz" "$output/ramdisk" "$output/kv260-revB.dtb"
fdtget "$output/kv260-revB.dtb" / model
fdtget "$output/kv260-revB.dtb" / compatible
printf 'BACKUP_COMPONENTS_EXTRACTED_NOT_NEW_BOOT_IMAGE\n'
