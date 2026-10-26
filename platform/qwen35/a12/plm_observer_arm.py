"""Compile the reviewed RO observer for A53 without stub headers or ARM execution."""
from pathlib import Path
import shutil
from plm_evidence import OUT,read,save,sha
from plm_build import run
def main():
    b=read(OUT/'BUILD-v4.json');r=read(OUT/'OBSERVER_REVIEWED-v2.json');w=Path(b['workspace']);src=w/'arm-observer-v2';src.mkdir()
    assert sha(w/'source/plm_observer.cpp')==r['source_sha256']
    for name in ('plm_page.hpp','pl_auth_gate.hpp','json.hpp'):shutil.copyfile(w/'arm-source'/name,src/name)
    shutil.copyfile(w/'source/plm_observer.cpp',src/'plm_observer.cpp')
    mapping=src/'exports.map';mapping.write_text('{ global: a12_plm_observe_fd_v1; local: *; };\n')
    library=w/'libplm_observer_ro_a53_v2.so';script=src/'build.sh'
    script.write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
read -r -a cc <<< "$CXX"
set -x
"${cc[@]}" -mcpu=cortex-a53 -std=c++17 -O2 -shared -fPIC -fvisibility=hidden -Wall -Wextra -Werror -I"'''+str(src)+'''" "'''+str(src/'plm_observer.cpp')+'''" -Wl,--version-script="'''+str(mapping)+'''" -Wl,-z,defs -o "'''+str(library)+'''"
"$READELF" -h -d --dyn-syms --wide "'''+str(library)+'''"
"$NM" -D --defined-only "'''+str(library)+'''"
''')
    result=run(['bash',script],'OBSERVER_ARM-v2',w);assert 'AArch64' in result.stdout
    save(OUT/'OBSERVER_ARM-v2.json.receipt',dict(status='PASS_A53_RO_OBSERVER_COMPILE_ONLY',library=str(library),sha256=sha(library),
        source_sha256=r['source_sha256'],script_sha256=sha(script),ARM_execution='NOT_EXECUTED',BOARD='NOT_TESTED'))
if __name__=='__main__':main()
