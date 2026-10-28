"""Compile the Board-domain consumer into the STILL hard-disabled XRT backend."""
import argparse
from pathlib import Path
import shutil
from generation_evidence import ROOT,OUT,PARENT,read,save,sha
from generation_build import run
from modelpl_derive import Derive

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);a=p.parse_args()
    b=read(OUT/f'BUILD-v{a.revision}.json');work=Path(b['workspace']);src=work/'arm-source';src.mkdir()
    old=Path(read(PARENT/'BUILD-v5.json')['workspace'])/'arm-private-backend'
    for name in ('host_contract.hpp','host_contract.cpp','release_gate.hpp','managed_lock.hpp','supervisor_gate.hpp','sp_linear_v1.h',
        'json.hpp','plm_page.hpp','plm_control.hpp','pl_auth_gate.hpp','private.map'):shutil.copyfile(old/name,src/name)
    shutil.copyfile(work/'source/generation_slot.hpp',src/'generation_slot.hpp')
    d=Derive((old/'backend.cpp').read_text());d.edit('#include "plm_control.hpp"','#include "generation_slot.hpp"')
    d.edit('    plm::Control authority;','    generation::Control<generation::BOARD> authority;')
    text,edits=d.finish();assert 'return SP_UNSUPPORTED;\n#endif\n    a12::permit("device_open",0);' in text
    (src/'backend.cpp').write_text(text)
    library=work/'liba12_generation_xrt_unbound.so';script=work/'build-generation-arm.sh'
    script.write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
test "$OECORE_SDK_VERSION" = 2026.1
set -x
aarch64-amd-linux-g++ --sysroot="$SDKTARGETSYSROOT" -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2 -std=c++17 -shared -fPIC -fno-fast-math -ffp-contract=off -Wall -Wextra -I"'''+str(src)+'''" "'''+str(src/'backend.cpp')+'''" "'''+str(src/'host_contract.cpp')+'''" -Wl,--version-script="'''+str(src/'private.map')+'''" -Wl,-z,defs -lxrt_coreutil -luuid -lcrypto -pthread -o "'''+str(library)+'''"
readelf -h -d --dyn-syms --wide "'''+str(library)+'''"
''')
    save(OUT/f'ARM_SOURCE-v{a.revision}.json',dict(original_XRT_backend_sha256=sha(old/'backend.cpp'),
        derived_sha256=sha(src/'backend.cpp'),reversible_edits=edits,source=[dict(name=p.name,sha256=sha(p)) for p in sorted(src.iterdir())],
        script_sha256=sha(script),Board_issuer='ABSENT',device_open='HARD_DISABLED'))
    run(['bash',script],f'ARM_BUILD-v{a.revision}',work,180)
    parent_arm=read(PARENT/'ARM_BUILD-v5.json')
    for row in parent_arm['artifacts']+parent_arm['original_math_before_and_after']:assert sha(row['path'])==row['sha256']
    save(OUT/f'ARM_RESULT-v{a.revision}.json',dict(status='PASS_A53_GENERATION_CONSUMER_COMPILE_ONLY',
        artifact=dict(path=str(library),sha256=sha(library),bytes=library.stat().st_size),ARM_execution='NOT_EXECUTED',
        Board_generation_approval='UNBOUND_NO_ISSUER',device_open='HARD_DISABLED_BEFORE_DEVICE_OPEN',private_begin_end='UNSUPPORTED',
        required_domain='BOARD_2_PC_SLOT_1_REFUSED',SP_A12_PC_TEST_defined=False,BOARD='NOT_TESTED',production_enabled=False))
if __name__=='__main__':main()
