#!/usr/bin/env bash
set -euo pipefail
src="$(cd "$(dirname "$0")" && pwd)"
out="${1:?provide a NEW absolute output directory}"
[[ "$out" = /* && ! -e "$out" ]] || exit 2
mkdir -p "$out"
gcc -std=c11 -O2 -Wall -Wextra -Werror "$src/cpu_smoke.c" -o "$out/cpu_smoke_pc"
"$out/cpu_smoke_pc"
set +u
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
read -r -a cc <<< "$CC"
set -x
"${cc[@]}" -mcpu=cortex-a53 -std=c11 -O2 -Wall -Wextra -Werror "$src/cpu_smoke.c" -o "$out/cpu_smoke_a53"
"$READELF" -h -l "$out/cpu_smoke_a53"
sha256sum "$out/cpu_smoke_a53" "$out/cpu_smoke_pc"
