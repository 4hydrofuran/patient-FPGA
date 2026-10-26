"""Snapshot, PC-double tests, then existing official SDK cross-build. No execution on ARM."""
import argparse
import os
import shutil
import subprocess
from pathlib import Path
from pl_auth_evidence import ROOT,OUT,WORK,BUNDLE,save,read,sha,pin
from pl_auth_derive import generate,PARENT_SHA

def command(argv,stem,cwd=None,timeout=120):
    r=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,text=True,timeout=timeout)
    save(OUT/(stem+'.json'),dict(command=[str(x) for x in argv],cwd=str(cwd),exit_code=r.returncode,
        stdout=r.stdout,stderr=r.stderr,BOARD='NOT_TESTED'))
    print(stem,r.returncode,flush=True)
    if r.returncode:print(r.stderr[-4000:]);raise SystemExit(r.returncode)
    return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--arm-only',action='store_true');p.add_argument('--sanitize',action='store_true');a=p.parse_args()
    assert os.name=='posix' and 1<=a.revision<=9
    work=WORK.with_name(WORK.name[:-1]+str(a.revision));src=work/'source'
    if not a.arm_only:
        os.umask(0o077);work.mkdir(mode=0o700,exist_ok=False);src.mkdir();(src/'xrt').mkdir()
        text,edits=generate();(src/'backend.cpp').write_text(text,encoding='utf-8')
        inputs=[]
        copies={
            'pl_auth_gate.hpp':ROOT/'platform/qwen35/a12/pl_auth_gate.hpp',
            'pl_auth_portable_probe.cpp':ROOT/'platform/qwen35/a12/pl_auth_portable_probe.cpp',
            'test_pl_auth.cpp':ROOT/'platform/qwen35/a12/test_pl_auth.cpp',
            'host_contract.hpp':ROOT/'modules/linear_A/xrt/host_contract.hpp',
            'host_contract.cpp':ROOT/'modules/linear_A/xrt/host_contract.cpp',
            'release_gate.hpp':ROOT/'modules/linear_A/xrt/release_gate.hpp',
            'managed_lock.hpp':ROOT/'platform/qwen35/a11/managed_lock.hpp',
            'sp_linear_v1.h':ROOT/'contracts/qwen35/sp_linear_v1.h',
            'supervisor_gate.hpp':BUNDLE/'source/supervisor_gate.hpp',
            'json.hpp':Path('/home/member-a/qwen35-a05/source-v3/vendor/nlohmann/json.hpp')}
        for name,path in copies.items():
            shutil.copyfile(path,src/name);inputs.append(dict(name=name,origin=str(path),sha256=sha(path)))
        stubs=ROOT/'platform/qwen35/a07/control/stubs'
        for name in ('xrt_device.h','xrt_kernel.h','xrt_bo.h'):shutil.copyfile(stubs/'xrt'/name,src/'xrt'/name)
        old=(stubs/'control_xrt.hpp').read_text();new=old.replace('inline void event(const std::string&name){events.push_back(name);fail(name);}',
            'inline void(*observer)(const std::string&)=nullptr;\ninline void event(const std::string&name){events.push_back(name);if(observer)observer(name);fail(name);}')
        assert new!=old;(src/'control_xrt.hpp').write_text(new)
        save(OUT/f'SNAPSHOT-v{a.revision}.json',dict(workspace=str(work),inputs=inputs,
            parent_backend_sha256=PARENT_SHA,derivation_reversible=True,edits=edits,
            source=[dict(name=x.relative_to(src).as_posix(),sha256=sha(x),bytes=x.stat().st_size) for x in sorted(src.rglob('*')) if x.is_file()],
            PC_XRT_doubles_not_math=True,ARM_activation='HARD_DISABLED_BEFORE_DEVICE_OPEN',BOARD='NOT_TESTED'))
        ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root')
        cmd=['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off','-DSP_LINEAR_CONTROL_TEST=1',
            '-I'+str(src),'-I'+str(ssl/'usr/include'),'-I'+str(ssl/'usr/include/x86_64-linux-gnu'),
            str(src/'test_pl_auth.cpp'),str(src/'backend.cpp'),str(src/'host_contract.cpp'),
            '-L'+str(ssl/'usr/lib/x86_64-linux-gnu'),'-Wl,-rpath,'+str(ssl/'usr/lib/x86_64-linux-gnu'),'-lcrypto','-pthread','-o',str(work/'pl-auth-control')]
        command(cmd,f'PC_BUILD-v{a.revision}',work)
        cases=['parent_loss','parent_loss_io','core','normal','reopen_generation','wrong_worker','wrong_binding','readonly','unbound','load_fault','preio_revoke','over_budget']
        cases+=['prestart_'+x for x in ('revoke','epoch','generation','context','health','deadline','budget')]
        cases+=['start_entry_revoke','postmeta_revoke','posty_revoke','timeout','start','state','set_arg','to_7','from_11','from_9',
            'stale','bad_job','bad_build','bad_count','bad_done','bad_bytes','private_error','nan_y','tail_y','device_error','device_abort','device_noresponse']
        results=[];directory=work/'cases';directory.mkdir()
        for mode in cases:
            c=directory/mode;c.mkdir();payload=b'PC DOUBLE ONLY, NOT A BITSTREAM\n';(c/'not-a-bitstream').write_bytes(payload);bit=sha(c/'not-a-bitstream')
            fixtures={
                'source.json':dict(provider='B',accepted=True,frozen=True,production_or_A07_link_allowed=True,selected_build_id='0xB3030002',xo_sha256='CONTROL_ONLY'),
                'profile.json':dict(status='CONTROL_TEST_ONLY_NOT_BOARD',source_xo_sha256='CONTROL_ONLY',xclbin_sha256=bit,xclbin_uuid='CONTROL_ONLY_UUID',
                    trial_bo_limit_bytes=10000000,bo_charge_alignment=8192,a12_max_runs=5000,a12_max_loads=72,kernel_build_id=0xB3030002,
                    device_index=0,device_name='CONTROL_ONLY_DEVICE',argument_groups=[5,3,7,7,9,11],argument_address_windows=[dict(base=0,span=10000000) for _ in range(6)]),
                'config.json':dict(api_version=1,contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',
                    backend_id='A_XRT_B_KERNEL_V1',fallback='disabled',kernel_source='source.json',deployment_profile='profile.json',allow_device_access=True,
                    xclbin_path='not-a-bitstream',xclbin_sha256=bit)}
            for name,v in fixtures.items():save(c/name,v)
            r=command([work/'pl-auth-control',mode,'config.json'],f'PC_CASE-v{a.revision}-{mode}',c,30)
            results.append(dict(case=mode,checks=read_result(r.stdout)['checks']))
        save(OUT/f'PC_SUMMARY-v{a.revision}.json',dict(status='PASS_PC_XRT_CONTROL_FLOW_ONLY',cases=results,checks=sum(x['checks'] for x in results),
            mathematical_verification=False,actual_FPGA_calls=None,BOARD='NOT_TESTED',production_enabled=False))
        if a.sanitize:
            san=cmd[:1]+['-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie']+cmd[1:-1]+[str(work/'pl-auth-control-sanitized')]
            command(san,f'SANITIZED_BUILD-v{a.revision}',work)
            sr=[];target=work/'sanitized-cases';target.mkdir()
            for mode in cases:
                c=target/mode;c.mkdir()
                for name in ('source.json','profile.json','config.json','not-a-bitstream'):
                    shutil.copyfile(directory/mode/name,c/name)
                r=command([work/'pl-auth-control-sanitized',mode,'config.json'],f'SANITIZED_CASE-v{a.revision}-{mode}',c,30)
                sr.append(dict(case=mode,checks=read_result(r.stdout)['checks']))
            save(OUT/f'SANITIZED_SUMMARY-v{a.revision}.json',dict(status='PASS_PC_ASAN_UBSAN_CONTROL_FLOW_ONLY',cases=sr,
                checks=sum(x['checks'] for x in sr),BOARD='NOT_TESTED',actual_FPGA_calls=None))
    # Neither stub headers nor SP_LINEAR_CONTROL_TEST is available to this compile.
    arm=work/'arm-source';arm.mkdir();
    for name in ('backend.cpp','pl_auth_gate.hpp','pl_auth_portable_probe.cpp','host_contract.hpp','host_contract.cpp','release_gate.hpp','managed_lock.hpp','sp_linear_v1.h','supervisor_gate.hpp','json.hpp'):
        shutil.copyfile(src/name,arm/name)
    shutil.copyfile(BUNDLE/'source/sp_abi.map',arm/'sp_abi.map')
    script=work/'cross-build.sh'
    script.write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
read -r -a cc <<< "$CXX"
set -x
"${cc[@]}" -mcpu=cortex-a53 -std=c++17 -O2 -fPIC -shared -fno-fast-math -ffp-contract=off -Wall -Wextra -Wl,-z,defs -Wl,--version-script="'''+str(arm/'sp_abi.map')+'''" -I"'''+str(arm)+'''" "'''+str(arm/'backend.cpp')+'''" "'''+str(arm/'host_contract.cpp')+'''" -o "'''+str(work/'liba12_pl_auth_unbound.so')+'''" -lxrt_coreutil -luuid -lcrypto -pthread
"${cc[@]}" -mcpu=cortex-a53 -std=c++17 -O2 -Wall -Wextra -Werror -I"'''+str(arm)+'''" -c "'''+str(arm/'pl_auth_portable_probe.cpp')+'''" -o "'''+str(work/'pl_auth_portable_probe.o')+'''"
"$NM" -u "'''+str(work/'pl_auth_portable_probe.o')+'''"
"$OBJDUMP" -d "'''+str(work/'pl_auth_portable_probe.o')+'''"
"$READELF" -h -d -Ws --wide "'''+str(work/'liba12_pl_auth_unbound.so')+'''"
''')
    command(['bash',str(script)],f'ARM_BUILD-v{a.revision}',work,120)
    binary=work/'liba12_pl_auth_unbound.so'
    save(OUT/f'ARTIFACTS-v{a.revision}.json',dict(status='PC_DOUBLE_AND_A53_COMPILE_ONLY',workspace=str(work),
        arm_library=str(binary),arm_sha256=sha(binary),pc_binary_sha256=sha(work/'pl-auth-control'),
        arm_full_gate_object=str(work/'pl_auth_portable_probe.o'),arm_full_gate_object_sha256=sha(work/'pl_auth_portable_probe.o'),
        cross_script_sha256=sha(script),BOARD='NOT_TESTED',production_enabled=False,real_device_generation_binding='UNBOUND'))
def read_result(t):
    import json
    return json.loads(t.strip().splitlines()[-1])
if __name__=='__main__':main()
