#!/usr/bin/env bash
# Download/extract Ubuntu host packages into a private PC build tree; no apt install.
set -euo pipefail
test "$(uname -m)" = x86_64
work=/home/member-a/a10-kernel-full-20261019-v1
test -d "$work/deps"
mkdir "$work/deps/downloads" "$work/deps/root"
cd "$work/deps/downloads"
apt-get download libelf-dev libssl-dev libssl3 pahole libbpf0 libdw1 libelf1
for package in *.deb; do
  dpkg-deb --info "$package" | sed -n '1,15p'
  sha256sum "$package"
  dpkg-deb -x "$package" "$work/deps/root"
done
printf 'PC_DEPENDENCIES_EXTRACTED_NO_SYSTEM_INSTALL\n'
LD_LIBRARY_PATH="$work/deps/root/usr/lib/x86_64-linux-gnu" "$work/deps/root/usr/bin/pahole" --version
