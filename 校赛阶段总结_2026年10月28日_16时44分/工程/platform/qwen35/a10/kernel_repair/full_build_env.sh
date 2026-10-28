#!/usr/bin/env bash
# Sourced only by PC build scripts; never an installer.
test "$(uname -m)" = x86_64 || return 1
work=/home/member-a/a10-kernel-full-20261019-v1
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS
export PATH="/usr/bin:/bin:$PATH"
deps=$work/deps/root
export LD_LIBRARY_PATH="$deps/usr/lib/x86_64-linux-gnu"
export KBUILD_BUILD_USER=a10-pc
export KBUILD_BUILD_HOST=isolated-candidate
export KBUILD_BUILD_TIMESTAMP='Mon Oct 19 00:00:00 UTC 2026'
export KBUILD_BUILD_VERSION=1
build_args=(-C "$work/source" O="$work/build" ARCH=arm64 CROSS_COMPILE=aarch64-amd-linux-
  CC=aarch64-amd-linux-gcc HOSTCC=/usr/bin/gcc HOSTCXX=/usr/bin/g++
  "HOSTCFLAGS=-I$deps/usr/include -I$deps/usr/include/x86_64-linux-gnu"
  "HOSTLDFLAGS=-L$deps/usr/lib/x86_64-linux-gnu -Wl,-rpath,$deps/usr/lib/x86_64-linux-gnu"
  "HOSTPKG_CONFIG=env PKG_CONFIG_SYSROOT_DIR=$deps PKG_CONFIG_LIBDIR=$deps/usr/lib/x86_64-linux-gnu/pkgconfig /usr/bin/pkg-config"
  "PAHOLE=$deps/usr/bin/pahole")
