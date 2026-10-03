#!/usr/bin/env bash
# PC test dependency only: extract official packages privately, never apt install.
set -euo pipefail
dest=/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30
test ! -e "$dest"
mkdir -p "$dest"
cd "$dest"
set -x
apt-get download libssl-dev=3.0.2-0ubuntu1.30 libssl3=3.0.2-0ubuntu1.30
sha256sum ./*.deb
for package in ./*.deb; do dpkg-deb --info "$package"; dpkg-deb --extract "$package" "$dest/root"; done
test -f root/usr/include/openssl/evp.h
test -f root/usr/lib/x86_64-linux-gnu/libcrypto.so.3
