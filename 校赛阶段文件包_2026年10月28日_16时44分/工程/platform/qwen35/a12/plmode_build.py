"""Compile a review-only A53 gated candidate; do not execute/install any ARM code."""
import argparse
import copy
import os
from pathlib import Path
import shutil
from plmode_evidence import ROOT,OUT,PARENT,WORK,read,save,sha
from modelpl_derive import Derive
from plmode_manager import CTOR_EDITS,REQUEST_EDITS,PAGE_EDITS
import subprocess

def run(argv,label,cwd=ROOT,timeout=180):
    argv=[str(x) for x in argv];r=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=timeout)
    save(OUT/(label+'.json'),dict(command=argv,cwd=str(cwd),exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));print(label,r.returncode,flush=True)
    if r.returncode:print(r.stderr[-3000:]);raise SystemExit(r.returncode)
    return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);a=p.parse_args();assert os.name=='posix' and 1<=a.revision<=9
    os.umask(0o077);w=WORK.with_name(WORK.name[:-1]+str(a.revision));w.mkdir();src=w/'arm-source';src.mkdir()
    parent=read(PARENT/'BUILD-v2.json');old=Path('/home/member-a/kv260-build/a12-generation-binding-20261026-v3/arm-source')
    frozen_source=read(ROOT/'evidence/model_pl_A/20261026-generation-binding-v1/ARM_SOURCE-v3.json')
    for row in frozen_source['source']:
        assert sha(old/row['name'])==row['sha256'];shutil.copyfile(old/row['name'],src/row['name'])
    # Same XRT math, BOs, sync, start, deadline, meta/Y validation and poison path.
    # The ONLY gate changes permit the existing private protocol in a separately
    # compiled candidate. The current/unbound binary remains hard disabled.
    d=Derive((src/'backend.cpp').read_text())
    d.edit('#ifndef SP_LINEAR_CONTROL_TEST\n    // This candidate cannot be activated on a board by editing a JSON enable flag.',
        '#if !defined(SP_LINEAR_CONTROL_TEST) && !defined(SP_A12_LIVE_BOARD_BOUND)\n    // This candidate cannot be activated on a board by editing a JSON enable flag.')
    # Unique surrounding text preserves the distinct PC-only test entry points.
    d.edit('#ifdef SP_LINEAR_CONTROL_TEST\n    require(digest);c->authority.bind_request(digest);return SP_OK;',
        '#if defined(SP_LINEAR_CONTROL_TEST) || defined(SP_A12_LIVE_BOARD_BOUND)\n    require(digest);c->authority.bind_request(digest);return SP_OK;')
    d.edit('#ifdef SP_LINEAR_CONTROL_TEST\n    c->authority.end_request();return SP_OK;',
        '#if defined(SP_LINEAR_CONTROL_TEST) || defined(SP_A12_LIVE_BOARD_BOUND)\n    c->authority.end_request();return SP_OK;')
    backend,edits=d.finish();(src/'backend.cpp').write_text(backend)
    shutil.copyfile(ROOT/'platform/qwen35/a12/plmode_observer.cpp',src/'plmode_observer.cpp')
    observer_map=src/'observer.map';observer_map.write_text('{ global: a12_plm_observe_fd_v1; local: *; };\n')
    save(OUT/f'SOURCE-v{a.revision}.json',dict(backend_reversible_edits=edits,original_backend_sha256=frozen_source['derived_sha256'],
        source=[dict(name=p.name,sha256=sha(p)) for p in sorted(src.iterdir())],constructor_edits=CTOR_EDITS,request_edits=REQUEST_EDITS,page_edits=PAGE_EDITS,
        physical_execution='NONE',deployment='NOT_PERFORMED'))
    candidate=w/'liba12_plmode_bound_candidate.so';disabled=w/'liba12_plmode_unbound.so'
    script=w/'compile-prepared-arm.sh';script.write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
test "$OECORE_SDK_VERSION" = 2026.1
set -x
for kind in unbound bound_candidate; do
  extra=()
  if test "$kind" = bound_candidate; then extra=(-DSP_A12_LIVE_BOARD_BOUND=1); fi
  aarch64-amd-linux-g++ --sysroot="$SDKTARGETSYSROOT" -mcpu=cortex-a53 -O2 -std=c++17 -shared -fPIC -fno-fast-math -ffp-contract=off -Wall -Wextra "${extra[@]}" -I"'''+str(src)+'''" "'''+str(src/'backend.cpp')+'''" "'''+str(src/'host_contract.cpp')+'''" -Wl,--version-script="'''+str(src/'private.map')+'''" -Wl,-z,defs -lxrt_coreutil -luuid -lcrypto -pthread -o "'''+str(w)+'''/liba12_plmode_${kind}.so"
  readelf -h -d --dyn-syms --wide "'''+str(w)+'''/liba12_plmode_${kind}.so"
done
aarch64-amd-linux-g++ --sysroot="$SDKTARGETSYSROOT" -mcpu=cortex-a53 -O2 -std=c++17 -shared -fPIC -fvisibility=hidden -I"'''+str(src)+'''" "'''+str(src/'plmode_observer.cpp')+'''" -Wl,--version-script="'''+str(observer_map)+'''" -lcrypto -o "'''+str(w/'libplmode_observer_a53.so')+'''"
''');run(['bash',script],f'ARM_BUILD-v{a.revision}',w)
    ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root');observer=w/'libplmode_observer.so'
    run(['g++','-std=c++17','-O2','-shared','-fPIC','-fvisibility=hidden','-I'+str(src),'-I'+str(ssl/'usr/include'),
        '-I'+str(ssl/'usr/include/x86_64-linux-gnu'),src/'plmode_observer.cpp','-Wl,--version-script='+str(observer_map),'-l:libcrypto.so.3','-o',observer],f'PC_OBSERVER-v{a.revision}',w)
    for row in parent['runtime_artifacts']+parent['manager_artifacts']:assert sha(row['path'])==row['sha256']
    pc=copy.deepcopy(parent);pc.update(workspace=str(w),prepared_Board_candidate=str(candidate),prepared_Board_candidate_sha256=sha(candidate),
        ARM_artifacts=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in (disabled,candidate,w/'libplmode_observer_a53.so')],
        observer_library=str(observer),observer_sha256=sha(observer),
        domain='PC_REAL_MODEL_PLM_V1',BOARD='NOT_TESTED',ARM_execution='NOT_EXECUTED',Board_deployed=False)
    save(OUT/f'BUILD-v{a.revision}.json',pc)
    save(OUT/f'BOARD_RUNTIME_LAYOUT-v{a.revision}.json',dict(status='PREPARED_MAPPING_NOT_AN_AUTHORIZED_RUNTIME_CONFIG',
        backend_artifact_sha256=sha(candidate),required_domain='A12_PREPARED_BOARD_MODEL_PLM_V1',
        required_fields=['native','runtime_artifacts','writer_library','writer_sha256','generation_writer','generation_writer_sha256','observer_library','observer_sha256',
            'backend_library','backend_sha256','prefix_template','prefix_libraries','library_search_path','model','kernel_source','xclbin'],
        original_native_and_math='REUSE_PINNED_A53_MODEL_ROUTE_BUILD_AND_ORDINARY_ASSETS',model_included=False,authorization_included=False,
        default_device_open='UNSUPPORTED',candidate_device_open='REQUIRES_ORIGINAL_LIVE_OWNER_LEASE_DUAL_LOCKS_AND_MANAGER_SOURCE',BOARD='NOT_TESTED'))
    print('PASS_A53_PREPARED_CANDIDATE_AND_DISABLED_BACKEND_COMPILE_ONLY')
if __name__=='__main__':main()
