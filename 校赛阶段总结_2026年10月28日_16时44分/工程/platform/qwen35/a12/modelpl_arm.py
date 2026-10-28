"""A53 native frontend/private ABI compile, with original hard-disabled XRT open."""
import argparse
from pathlib import Path
import shutil
from modelpl_evidence import ROOT,OUT,read,save,sha
from modelpl_build import run

ABORT=r'''
extern "C" int32_t sp_a12_plm_request_abort_v1(sp_linear_context*c)try{
    auto lock=locked(c);c->authority.fail();c->life.poison();
    c->last={{"last_status_code",SP_POISONED},{"output_consumable",false}};return SP_POISONED;
}catch(...){return error();}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);a=p.parse_args();b=read(OUT/f'BUILD-v{a.revision}.json');w=Path(b['workspace'])
    src=w/'source';arm=w/'arm-private-backend';arm.mkdir();parent=read(ROOT/'evidence/model_pl_A/20261026-pl-manager-v1/BUILD-v4.json')
    old=Path(parent['workspace'])/'arm-source'
    for name in ('host_contract.hpp','host_contract.cpp','release_gate.hpp','managed_lock.hpp','supervisor_gate.hpp','sp_linear_v1.h','json.hpp','plm_page.hpp','plm_control.hpp','pl_auth_gate.hpp'):
        shutil.copyfile(old/name,arm/name)
    text=(old/'backend.cpp').read_text();assert 'return SP_UNSUPPORTED;\n#endif\n    a12::permit("device_open",0);' in text
    (arm/'backend.cpp').write_text(text+ABORT)
    public=(old/'sp_abi.map').read_text();mapping=public+'''\nA12_PLM_PRIVATE_V1 {
  global: sp_a12_plm_request_v1; sp_a12_plm_request_end_v1; sp_a12_plm_request_abort_v1;
} SP_LINEAR_V1;
'''
    (arm/'private.map').write_text(mapping)
    old_native=Path('/home/member-a/kv260-build/a12-tt10-01-20261024-v1');objects=list((old_native/'arm04/CMakeFiles').rglob('w4a8.cpp.o'));assert len(objects)==1
    first=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json');second=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json')
    llama=Path(first['workspace'])/'arm-llama';base=Path(second['workspace'])/'model';q=objects[0]
    math=[q,base/'libsp_linear_cpu.so']+[llama/'bin'/x for x in ('libllama.so','libggml.so','libggml-base.so','libggml-cpu.so')]
    before=[dict(path=str(p.resolve()),sha256=sha(p),bytes=p.stat().st_size) for p in math]
    script=w/'build-arm-private.sh';script.write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
test "$OECORE_SDK_VERSION" = 2026.1
export CC=aarch64-amd-linux-gcc CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS" CPPFLAGS=""
cmake -S "'''+str(w/'cmake')+'''" -B "'''+str(w/'arm')+'''" -DCMAKE_TOOLCHAIN_FILE="$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake" -DCMAKE_BUILD_TYPE=Release -DROOT=/mnt/c/Patientqwen -DA12_SOURCE="'''+str(src)+'''" -DASSET_ROOT=/opt/patient-qwen -DLLAMA_SOURCE="'''+str(Path(first['workspace'])/'llama-source')+'''" -DLLAMA_BUILD="'''+str(llama)+'''" -DBASE_BUILD="'''+str(base)+'''" -DEXISTING_QUANT_OBJECT="'''+str(q)+'''"
cmake --build "'''+str(w/'arm')+'''" -j4
set -x
aarch64-amd-linux-g++ $CXXFLAGS -std=c++17 -shared -fPIC -fno-fast-math -ffp-contract=off -Wall -Wextra -I"'''+str(arm)+'''" "'''+str(arm/'backend.cpp')+'''" "'''+str(arm/'host_contract.cpp')+'''" -Wl,--version-script="'''+str(arm/'private.map')+'''" -Wl,-z,defs -lxrt_coreutil -luuid -lcrypto -pthread -o "'''+str(w/'liba12_modelpl_xrt_unbound.so')+'''"
readelf -h -d --dyn-syms --wide "'''+str(w/'liba12_modelpl_xrt_unbound.so')+'''"
readelf -h -d --wide "'''+str(w/'arm/qwen35-a12')+'''"
''')
    run(['bash',script],f'ARM_NATIVE_PRIVATE_BUILD-v{a.revision}',w,240)
    for row in before:assert sha(row['path'])==row['sha256']
    artifacts=[w/'arm/qwen35-a12',w/'liba12_modelpl_xrt_unbound.so']
    save(OUT/f'ARM_BUILD-v{a.revision}.json',dict(status='PASS_A53_NATIVE_FRONT_ROUTE_AND_PRIVATE_BACKEND_COMPILE_ONLY',artifacts=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in artifacts],
        original_math_before_and_after=before,original_XRT_backend_sha256=sha(old/'backend.cpp'),derived_XRT_backend_sha256=sha(arm/'backend.cpp'),
        private_ABI_namespace='A12_PLM_PRIVATE_V1',public_contract_unchanged=True,ARM_execution='NOT_EXECUTED',production_open='HARD_DISABLED_BEFORE_DEVICE_OPEN',
        CPU_math_adapter='X86_PC_ONLY_NOT_BUILT_FOR_ARM',BOARD='NOT_TESTED',production_enabled=False))
if __name__=='__main__':main()
