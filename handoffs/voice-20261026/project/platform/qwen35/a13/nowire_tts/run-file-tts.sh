#!/usr/bin/env bash
# File synthesis only. No installation, hardware setup or audio-device open.
set -euo pipefail
bundle_a13=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
if [[ $(uname -m) != aarch64 ]]; then
    printf '%s\n' 'ARM64 target required; this is not the PC test launcher' >&2
    exit 2
fi
python3 -B -c 'import sys; assert sys.version_info[:2] == (3,12), "CPython3.12 required"'
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$bundle_a13/code:$bundle_a13/site-packages"
exec python3 -s -B -m modules.voice_A.file_tts --root "$bundle_a13" "$@"
