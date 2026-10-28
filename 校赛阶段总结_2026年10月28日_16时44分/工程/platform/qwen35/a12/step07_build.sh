#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
evidence=$repo/evidence/model_pl_A/20261023-step07-single-v1
prior=/home/member-a/kv260-build/ra02-coordinator/work/01792765652209098616-A-a12-model-arm-final-v2-61fd3319
llama=$(python3 -c 'import json;from pathlib import Path;r=json.load(open("/mnt/c/Patientqwen/evidence/model_pl_A/20261023-preboard-v1/ARM_BUILD_FINAL.json"));print(Path(r["files"]["libllama.so"]["path"]).parent.parent)')
cmake -S "$repo/platform/qwen35/a12" -B "$PWD/pc" -DCMAKE_BUILD_TYPE=Release -DA12_SOURCE="$evidence/source-v1"
cmake --build "$PWD/pc" -j4
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
test "$OECORE_SDK_VERSION" = 2026.1
export CC=aarch64-amd-linux-gcc
export CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS"
export CPPFLAGS=""
tc=$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake
cmake -S "$repo/platform/qwen35/a12" -B "$PWD/model" -DCMAKE_TOOLCHAIN_FILE="$tc" -DCMAKE_BUILD_TYPE=Release \
 -DA12_SOURCE="$evidence/source-v1" -DASSET_ROOT=/opt/patient-qwen \
 -DLLAMA_SOURCE=/home/member-a/qwen35-a05/source-v3 -DLLAMA_BUILD="$llama"
cmake --build "$PWD/model" -j4
xrt218=/home/member-a/a10-driver-audit-20261018/xrt-userspace/usr
read -r -a compiler <<< "$CXX"
"${compiler[@]}" $CXXFLAGS -std=c++17 -O2 -fno-fast-math -ffp-contract=off -Wall -Wextra -Werror -fPIC -shared \
 -I"$xrt218/include/xrt" -I"$repo/contracts/qwen35" -I"$repo/modules/linear_A/xrt" \
 -I"$repo/release/a07_b04_v3/third_party/nlohmann" -I"$repo/platform/qwen35/a11" \
 -I"$evidence/source-v1" "$evidence/source-v1/backend.cpp" "$repo/modules/linear_A/xrt/host_contract.cpp" \
 "$xrt218/lib/libxrt_coreutil.so.2.18.0" -luuid -lcrypto -pthread -Wl,-z,defs -Wl,-Bsymbolic-functions \
 -Wl,--version-script="$evidence/source-v1/sp_abi.map" -Wl,-soname,libsp_linear_a12_trial.so \
 -o "$PWD/libsp_linear_a12_trial.so"
python3 - "$evidence" <<'PY'
import hashlib,json,subprocess,sys
from pathlib import Path
e=Path(sys.argv[1]);w=Path.cwd();rows={}
for p in (w/'model/qwen35-a12',w/'model/libsp_linear_cpu.so',w/'libsp_linear_a12_trial.so'):
 h=subprocess.check_output(['readelf','-h',str(p)],text=True);assert 'AArch64' in h
 d=subprocess.check_output(['readelf','-d',str(p)],text=True)
 if p.name.startswith('libsp_linear'):
  symbols=subprocess.check_output(['nm','-D','--defined-only',str(p)],text=True)
  assert sum(' sp_linear_' in line for line in symbols.splitlines())==6
 rows[p.name]=dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),header=h,dynamic=d)
with (e/'BUILD.json').open('x') as f:json.dump(dict(workspace=str(w),pc=str(w/'pc/qwen35-a12'),files=rows,domain='PC_AND_CROSS_BUILD_NOT_BOARD',math_changed=False),f,indent=2)
PY
