#!/bin/bash
# Isolated cross-build only. Never modules_install, depmod, modprobe or insmod.
set -euo pipefail
test "$(uname -m)" = x86_64
test "$PWD" = /home/member-a/a13-muted-headers1036-20261025-v1/build-01
exec 9>build.lock
flock -n 9
kernel="$PWD/headers/linux-headers-6.8.0-1036-xilinx"
test "$(sha256sum "$kernel/.config" | cut -d ' ' -f1)" = d0937ab5ab55818252854b3b91d291148c89011e4e5d9f4e2cc134e4c3d9610f
test "$(sha256sum "$kernel/Module.symvers" | cut -d ' ' -f1)" = 860c5609e229079a4836ec694447b89c9aa8ac42c26c0f1f5672d859f8cd1de1
# Only the copied ARM host helpers are rebuilt for x86. Original package tree is untouched.
( cd "$kernel"
  /usr/bin/gcc -O2 -o scripts/basic/fixdep scripts/basic/fixdep.c
  /usr/bin/gcc -O2 -I scripts/mod -o scripts/mod/modpost scripts/mod/modpost.c scripts/mod/file2alias.c scripts/mod/sumversion.c scripts/mod/symsearch.c
  /usr/bin/gcc -O2 -I scripts/genksyms -o scripts/genksyms/genksyms scripts/genksyms/genksyms.c scripts/genksyms/parse.tab.c scripts/genksyms/lex.lex.c
)
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS
export PATH=/usr/bin:$PATH
make -C "$kernel" M="$PWD/modules" ARCH=arm64 CROSS_COMPILE=aarch64-amd-linux- CC=aarch64-amd-linux-gcc HOSTCC=/usr/bin/gcc W=1 -j2 modules
for candidate in modules/*.ko;do
    aarch64-amd-linux-readelf -h "$candidate"
    /sbin/modinfo "$candidate"
done
test "$(sha256sum "$kernel/.config" | cut -d ' ' -f1)" = d0937ab5ab55818252854b3b91d291148c89011e4e5d9f4e2cc134e4c3d9610f
test "$(sha256sum "$kernel/Module.symvers" | cut -d ' ' -f1)" = 860c5609e229079a4836ec694447b89c9aa8ac42c26c0f1f5672d859f8cd1de1
