"""Build separated backend/router/writer/probe artifacts, preserving frozen inputs."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from plm_evidence import ROOT,OUT,WORK,read,save,sha
from plm_derive import generate

def run(argv,name,cwd,timeout=120):
    r=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,text=True,timeout=timeout)
    save(OUT/(name+'.json'),dict(command=[str(x) for x in argv],cwd=str(cwd),exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
    print(name,r.returncode,flush=True)
    if r.returncode:print(r.stderr[-5000:]);raise SystemExit(r.returncode)
    return r
def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--sanitize',action='store_true');a=p.parse_args();need=1<=a.revision<=9;assert need and os.name=='posix'
    work=WORK.with_name(WORK.name[:-1]+str(a.revision));os.umask(0o077);work.mkdir(mode=0o700);src=work/'source';src.mkdir();(src/'xrt').mkdir()
    parent=read(ROOT/'evidence/model_pl_A/20261026-pl-auth-binding-v1/ARTIFACTS-v4.json');old=Path(parent['workspace'])/'source'
    snap=read(ROOT/'evidence/model_pl_A/20261026-pl-auth-binding-v1/SNAPSHOT-v4.json')
    for r in snap['source']:assert sha(old/r['name'])==r['sha256']
    text,edits=generate();(src/'backend.cpp').write_text(text)
    for name in ('pl_auth_gate.hpp','host_contract.hpp','host_contract.cpp','release_gate.hpp','managed_lock.hpp','sp_linear_v1.h','json.hpp','control_xrt.hpp'):
        shutil.copyfile(old/name,src/name)
    for name in ('xrt_bo.h','xrt_device.h','xrt_kernel.h'):shutil.copyfile(old/'xrt'/name,src/'xrt'/name)
    for name in ('plm_page.hpp','plm_control.hpp','plm_writer.cpp','plm_probe.cpp','plm_router_shim.cpp','plm_portable_probe.cpp','plm_observer.cpp'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,src/name)
    gate=(old/'supervisor_gate.hpp').read_text();start=gate.index('#ifdef SP_LINEAR_CONTROL_TEST');end=gate.index('#else',start)
    actual=gate[:start]+gate[end+len('#else'):];actual=actual.replace('\n#endif\n}', '\n}')
    assert '#ifdef SP_LINEAR_CONTROL_TEST' not in actual and '#endif' not in actual
    (src/'supervisor_gate.hpp').write_text(actual) # exercise actual SO_PEERCRED/sequence wire, even with XRT doubles
    save(OUT/f'SNAPSHOT-v{a.revision}.json',dict(workspace=str(work),parent_backend_sha256=sha(old/'backend.cpp'),derivation_reversible=True,edits=edits,
        source=[dict(name=p.relative_to(src).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(src.rglob('*')) if p.is_file()],
        original_gate_sha256=sha(old/'supervisor_gate.hpp'),legacy_production_body_unchanged=True,BOARD='NOT_TESTED'))
    ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root')
    common=['g++','-std=c++17','-O2','-fPIC','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off','-I'+str(src),
        '-I'+str(ssl/'usr/include'),'-I'+str(ssl/'usr/include/x86_64-linux-gnu')]
    deps=['-L'+str(ssl/'usr/lib/x86_64-linux-gnu'),'-Wl,-rpath,'+str(ssl/'usr/lib/x86_64-linux-gnu'),'-lcrypto','-pthread']
    backend=work/'libplm_backend_pc_control.so';router=work/'libplm_router_legacy_probe.so';writer=work/'libplm_writer.so';probe=work/'plm-control-probe';observer=work/'libplm_observer_ro.so'
    san=['-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-fno-omit-frame-pointer'] if a.sanitize else []
    public=['sp_linear_open_v1','sp_linear_load_v1','sp_linear_run_v1','sp_linear_report_v1','sp_linear_unload_v1','sp_linear_close_v1','sp_a12_completion_report_v1']
    private=['sp_a12_plm_request_v1','sp_a12_plm_request_end_v1','sp_a12_plm_test_fault_v1','sp_a12_plm_test_inventory_v1']
    (work/'pc.map').write_text('PC_PLM_CONTROL_V1 { global: '+'; '.join(public+private)+'; local: *; };\n')
    run(common+san+['-shared','-DSP_LINEAR_CONTROL_TEST=1',src/'backend.cpp',src/'host_contract.cpp','-o',backend,'-Wl,--version-script='+str(work/'pc.map'),'-Wl,-z,defs']+deps,f'BACKEND_BUILD-v{a.revision}',work)
    run(common+san+['-shared','-fvisibility=hidden',src/'plm_router_shim.cpp','-o',router]+deps,f'ROUTER_BUILD-v{a.revision}',work)
    writer_san=['-fsanitize=undefined','-fno-sanitize-recover=undefined'] if a.sanitize else []
    run(common+writer_san+['-shared','-fvisibility=hidden',src/'plm_writer.cpp','-o',writer]+deps,f'WRITER_BUILD-v{a.revision}',work)
    observer_map=work/'observer-exports.map';observer_map.write_text('{ global: a12_plm_observe_fd_v1; local: *; };\n')
    run(common+['-shared','-fvisibility=hidden',src/'plm_observer.cpp','-Wl,--version-script='+str(observer_map),'-o',observer]+deps,f'OBSERVER_BUILD-v{a.revision}',work)
    run(common+san+(['-no-pie'] if a.sanitize else [])+[src/'plm_probe.cpp','-L'+str(work),'-lplm_backend_pc_control','-Wl,-rpath,'+str(work),'-o',probe,'-ldl']+deps,f'PROBE_BUILD-v{a.revision}',work)
    arm=work/'arm-source';arm.mkdir()
    for name in ('backend.cpp','host_contract.cpp','host_contract.hpp','release_gate.hpp','managed_lock.hpp','sp_linear_v1.h','json.hpp','supervisor_gate.hpp','pl_auth_gate.hpp','plm_page.hpp','plm_control.hpp','plm_writer.cpp','plm_portable_probe.cpp'):
        shutil.copyfile(src/name,arm/name)
    shutil.copyfile(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2/source/sp_abi.map',arm/'sp_abi.map')
    script=work/'build-arm.sh';script.write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
set -u
read -r -a cc <<< "$CXX"
set -x
"${cc[@]}" -mcpu=cortex-a53 -std=c++17 -O2 -shared -fPIC -fno-fast-math -ffp-contract=off -Wall -Wextra -I"'''+str(arm)+'''" "'''+str(arm/'backend.cpp')+'''" "'''+str(arm/'host_contract.cpp')+'''" -Wl,--version-script="'''+str(arm/'sp_abi.map')+'''" -Wl,-z,defs -lxrt_coreutil -lcrypto -luuid -pthread -o "'''+str(work/'libplm_a53_unbound.so')+'''"
"${cc[@]}" -mcpu=cortex-a53 -std=c++17 -O2 -shared -fPIC -fvisibility=hidden -Wall -Wextra -Werror -I"'''+str(arm)+'''" "'''+str(arm/'plm_writer.cpp')+'''" -Wl,-z,defs -pthread -o "'''+str(work/'libplm_writer_a53.so')+'''"
"${cc[@]}" -mcpu=cortex-a53 -std=c++17 -O2 -Wall -Wextra -Werror -I"'''+str(arm)+'''" -c "'''+str(arm/'plm_portable_probe.cpp')+'''" -o "'''+str(work/'plm_full_protocol_a53.o')+'''"
"$READELF" -h -d -Ws --wide "'''+str(work/'libplm_a53_unbound.so')+'''"
"$READELF" -h -d -Ws --wide "'''+str(work/'libplm_writer_a53.so')+'''"
"$NM" -u "'''+str(work/'plm_full_protocol_a53.o')+'''"
''')
    run(['bash',script],f'ARM_BUILD-v{a.revision}',work)
    paths=[backend,router,writer,probe,observer]
    save(OUT/f'BUILD-v{a.revision}.json',dict(domain='PC_XRT_CONTROL_ONLY_A53_UNBOUND',workspace=str(work),revision=a.revision,
        probe=str(probe),backend_library=str(backend),router_library=str(router),writer_library=str(writer),writer_sha256=sha(writer),observer_library=str(observer),
        sanitizers=dict(probe_backend_router='ASAN_UBSAN' if a.sanitize else 'NONE',manager_writer='UBSAN' if a.sanitize else 'NONE',leak_check=False),
        artifacts=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in paths],source_snapshot_sha256=sha(OUT/f'SNAPSHOT-v{a.revision}.json'),
        ARM_artifacts=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in [work/'libplm_a53_unbound.so',work/'libplm_writer_a53.so',work/'plm_full_protocol_a53.o']],
        BOARD='NOT_TESTED',production_enabled=False,real_device_generation_approval='UNBOUND'))
if __name__=='__main__':main()
