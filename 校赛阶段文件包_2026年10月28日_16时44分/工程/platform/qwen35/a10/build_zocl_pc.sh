#!/usr/bin/env bash
# PC-only precompile, never install/load. Fixed isolated extracted inputs.
set -euo pipefail
test "$(uname -m)" = x86_64
audit=/home/member-a/a10-driver-audit-20261018
kernel="$audit/headers/usr/src/linux-headers-6.8.0-1015-xilinx"
driver="$audit/source/usr/src/xrt-2.18.0/driver/zocl"
test "$(sha256sum "$kernel/.config" | cut -d ' ' -f1)" = 6ebb559a50a68b26bd0a681ea010264525af09cc4faa7814abfc0a1ddd20ff2e
test "$(sha256sum "$kernel/Module.symvers" | cut -d ' ' -f1)" = 7e93bbb17224ef84a9641c4fca7481323adf5dca4b3f46329327707003a818b3
# Rebuild only host helper executables from the exact header package's C sources.
# This does not alter target config, symvers, driver C, headers, or installed system.
cd "$kernel"
/usr/bin/gcc -O2 -o scripts/basic/fixdep scripts/basic/fixdep.c
/usr/bin/gcc -O2 -I scripts/mod -o scripts/mod/modpost scripts/mod/modpost.c scripts/mod/file2alias.c scripts/mod/sumversion.c scripts/mod/symsearch.c
/usr/bin/gcc -O2 -I scripts/genksyms -o scripts/genksyms/genksyms scripts/genksyms/genksyms.c scripts/genksyms/parse.tab.c scripts/genksyms/lex.lex.c
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
# Use kernel's own flags, not SDK userspace A72 flags or -march=native.
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS
cd "$driver"
timeout 120s make -j2 KERNEL_SRC="$kernel" ARCH=arm64 CROSS_COMPILE=aarch64-amd-linux- CC=aarch64-amd-linux-gcc HOSTCC=/usr/bin/gcc \
    GIT_HASH=debian-xrt-2.18.0-0ubuntu1 GIT_HASH_DATE=package-source GIT_BRANCH=pc-audit GIT_MODIFIED_FILES=none DATE_NOW=2026-10-18 modules
file zocl.ko
sha256sum zocl.ko "$kernel/.config" "$kernel/Module.symvers"
/sbin/modinfo ./zocl.ko
