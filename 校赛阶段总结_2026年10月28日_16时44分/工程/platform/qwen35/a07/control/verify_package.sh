#!/usr/bin/env bash
# Runs only PC controls and ARM cross-builds in an isolated queue work directory.
set -euo pipefail
repo=/mnt/c/Patientqwen
package="$repo/release/a07_b04_v3"
test -f "$package/files.sha256.json"
python3 "$repo/platform/qwen35/a07/control/verify_hashes.py" "$package"
cp -a "$package" delivery
root="$PWD/delivery"
mkdir portable-build control-build
cd portable-build
bash "$root/platform/qwen35/a07/b04/build_portable.sh" "$root" "$root/third_party/nlohmann" \
 /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
cd ../control-build
bash "$root/platform/qwen35/a07/control/build_control_portable.sh" "$root" \
 /home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root/usr
cd ..
python3 "$root/hw/linear_B_received/B04-scope-9a75600-20261003/tools/b04_a_preflight.py" "$root" \
 --readelf /usr/bin/readelf --receipt "$PWD/B-preflight.json"
python3 "$repo/platform/qwen35/a07/control/verify_hashes.py" "$root"
