#!/usr/bin/env bash
# Offline build queue only. No device discovery or ARM execution.
set -euo pipefail
repo=/mnt/c/Patientqwen
evidence=$repo/evidence/model_pl_A/20261023-preboard-v1
version=${1:-v2}
python3 -B "$repo/platform/qwen35/a12/prepare_source.py" --out "$evidence/source-$version"
cmake -S "$repo/platform/qwen35/a12" -B "$PWD/pc" -DCMAKE_BUILD_TYPE=Release -DA12_SOURCE="$evidence/source-$version"
cmake --build "$PWD/pc" -j4
python3 -c 'import json,sys; from pathlib import Path; p=Path(sys.argv[1]); p.open("x").write(json.dumps({"pc_build":str(Path.cwd()/"pc"),"domain":"PC_COMPILE_ONLY","BOARD":"NOT_TESTED"},indent=2))' "$evidence/PC_BUILD-$version.json"
