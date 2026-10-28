#!/usr/bin/env bash
set -eo pipefail
repo=/mnt/c/Patientqwen
evidence=$repo/evidence/model_pl_A/20261023-preboard-v1
prior=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["workspace"])' "$evidence/ARM_BUILD.json")
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
src=/home/member-a/qwen35-a05/source-v3
tc=$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake
export CC=aarch64-amd-linux-gcc
export CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS"
export CPPFLAGS=""
# Model trace changed; fixed llama and backend sources did not. Reuse only pinned outputs.
python3 - "$evidence" "$prior" <<'PY'
import hashlib,json,sys
from pathlib import Path
e=Path(sys.argv[1]);r=json.loads((e/'ARM_BUILD.json').read_text())
for name,row in r['files'].items():
    p=Path(row['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
assert (e/'source-v4/backend.cpp').read_bytes()==(e/'source-v3/backend.cpp').read_bytes()
for name,digest in r['final_sources'].items():
    assert hashlib.sha256((Path('/home/member-a/qwen35-a05/source-v3')/name).read_bytes()).hexdigest()==digest
PY
cmake -S "$repo/platform/qwen35/a12" -B "$PWD/model" \
 -DCMAKE_TOOLCHAIN_FILE="$tc" -DCMAKE_BUILD_TYPE=Release \
 -DA12_SOURCE="$evidence/source-v4" -DASSET_ROOT=/opt/patient-qwen \
 -DLLAMA_SOURCE="$src" -DLLAMA_BUILD="$prior/llama"
cmake --build "$PWD/model" -j4
cp "$prior/libsp_linear_a12_trial.so" "$PWD/libsp_linear_a12_trial.so"
python3 -B "$repo/platform/qwen35/a12/audit_arm.py" "$PWD" "$prior/llama" ARM_BUILD_FINAL.json
