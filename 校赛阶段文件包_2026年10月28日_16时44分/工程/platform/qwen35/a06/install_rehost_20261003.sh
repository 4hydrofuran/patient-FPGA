#!/bin/bash
set -euo pipefail
source_license='/mnt/d/EdgeDownload/Xilinx (1).lic'
target_license='/home/member-a/.Xilinx/kv260-a-rehost-20261003.lic'
expected='46ef2a17d5100e55d7181a8e9b7acc4d79580852a921cdea6c5eeccb33bf177f'
test "$(sha256sum "$source_license" | cut -d ' ' -f 1)" = "$expected"
test "$(tr -d ':\n' </sys/class/net/eth0/address)" = '00155dbc2453'
test -d /home/member-a/.Xilinx
test ! -L /home/member-a/.Xilinx
test ! -e "$target_license"
test ! -L "$target_license"
install -m 600 -- "$source_license" "$target_license"
test "$(sha256sum "$target_license" | cut -d ' ' -f 1)" = "$expected"
printf 'Installed official rehost license; original unchanged; mode=600\n'
sha256sum "$target_license"
