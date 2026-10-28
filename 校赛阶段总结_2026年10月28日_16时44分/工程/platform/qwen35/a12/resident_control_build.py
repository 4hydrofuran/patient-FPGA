"""Separate nine-request private control artifacts; all compute math is reused."""
import copy
import os
from pathlib import Path
import shutil
from resident_evidence import ROOT,OUT,WORK,read,save,sha
from resident_native import run
from modelpl_derive import Derive

def headers(folder):
    edits={}
    for name,changes in [
        ('plm_page.hpp',[("e->request_serial.load()<3","e->request_serial.load()<9"),('gen<=4','gen<=10')]),
        ('plm_control.hpp',[('generation<=4','generation<=10'),('extra(p)->request_serial.load()==3',
            '(extra(p)->request_serial.load()>=1&&extra(p)->request_serial.load()<=9)'),
            ('{{"schema","PC_PLM_BACKEND_CONTROL_V1"},{"batches",batches}', '{{"schema","PC_PLM_BACKEND_CONTROL_V1"},{"request_limit",9},{"batches",batches}')])]:
        d=Derive((folder/name).read_text())
        for old,new in changes:d.edit(old,new)
        text,edits[name]=d.finish();(folder/name).write_text(text)
    return edits

def main():
    assert os.name=='posix';w=WORK/'control-v1';w.mkdir();pc=w/'pc-source';arm=w/'arm-source';pc.mkdir();arm.mkdir()
    old=read(ROOT/'evidence/model_pl_A/20261026-generation-binding-v1/BUILD-v3.json');old_dir=Path(old['workspace'])/'source'
    for row in old['generation_source']:
        p=old_dir/row['name'];assert sha(p)==row['sha256'];shutil.copyfile(p,pc/row['name'])
    shutil.copyfile(ROOT/'platform/qwen35/a12/plm_writer.cpp',pc/'plm_writer.cpp')
    text=(pc/'plm_writer.cpp').read_text();(pc/'plm_writer.cpp').write_text(text+'\nPLM_API int a12_resident_request_limit_v1(){return 9;}\n')
    cpp=pc/'generation_cpu.cpp';cpp.write_text(cpp.read_text()+'\nextern "C" __attribute__((visibility("default"))) int sp_a12_resident_request_limit_v1(){return 9;}\n')
    pc_edits=headers(pc)
    mode=read(ROOT/'evidence/model_pl_A/20261026-pl-mode-v1/BUILD-v2.json');mode_source=Path(mode['workspace'])/'arm-source'
    mode_pins=read(ROOT/'evidence/model_pl_A/20261026-pl-mode-v1/SOURCE-v2.json')['source']
    for row in mode_pins:
        p=mode_source/row['name'];assert sha(p)==row['sha256'];shutil.copyfile(p,arm/row['name'])
    shutil.copyfile(pc/'plm_writer.cpp',arm/'plm_writer.cpp');arm_edits=headers(arm)
    cpp=arm/'backend.cpp';cpp.write_text(cpp.read_text()+'\nextern "C" __attribute__((visibility("default"))) int sp_a12_resident_request_limit_v1(){return 9;}\n')
    m=arm/'private.map';m.write_text(m.read_text()+'\nA12_RESIDENT_CONTROL_V1 { global: sp_a12_resident_request_limit_v1; } A12_PLM_PRIVATE_V1;\n')
    save(OUT/'CONTROL_SOURCE-v1.json',dict(pc_edits=pc_edits,arm_edits=arm_edits,
        PC=[dict(name=p.name,sha256=sha(p)) for p in sorted(pc.iterdir())],ARM=[dict(name=p.name,sha256=sha(p)) for p in sorted(arm.iterdir())],
        private_request_limit=9,total_runs_unchanged=5000,health_age_ns_unchanged=250000000,source_slot_domains_unchanged=True,
        public_ABI_unchanged=True,math_changed=False,ARM_execution='NOT_EXECUTED'))
    ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root');lib=w/'liba12_native_cpu_control.so';writer=w/'libplm_writer.so'
    flags=['g++','-std=c++17','-O2','-shared','-fPIC','-fvisibility=hidden','-DSP_A12_PC_TEST=1','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra',
        '-I'+str(pc),'-I'+str(ssl/'usr/include'),'-I'+str(ssl/'usr/include/x86_64-linux-gnu')]
    run(flags+[pc/'generation_cpu.cpp','-o',lib,'-ldl','-l:libcrypto.so.3'],'CONTROL_PC_ADAPTER-v1',w)
    run(flags+[pc/'plm_writer.cpp','-o',writer,'-l:libcrypto.so.3'],'CONTROL_PC_WRITER-v1',w)
    script=w/'build-arm-control.sh';script.write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
test "$OECORE_SDK_VERSION" = 2026.1
set -x
for kind in unbound bound_candidate; do
  extra=()
  if test "$kind" = bound_candidate; then extra=(-DSP_A12_LIVE_BOARD_BOUND=1); fi
  aarch64-amd-linux-g++ --sysroot="$SDKTARGETSYSROOT" -mcpu=cortex-a53 -O2 -std=c++17 -shared -fPIC -fno-fast-math -ffp-contract=off -Wall -Wextra "${extra[@]}" -I"'''+str(arm)+'''" "'''+str(arm/'backend.cpp')+'''" "'''+str(arm/'host_contract.cpp')+'''" -Wl,--version-script="'''+str(arm/'private.map')+'''" -Wl,-z,defs -lxrt_coreutil -luuid -lcrypto -pthread -o "'''+str(w)+'''/liba12_resident_${kind}.so"
done
aarch64-amd-linux-g++ --sysroot="$SDKTARGETSYSROOT" -mcpu=cortex-a53 -O2 -std=c++17 -shared -fPIC -fvisibility=hidden -I"'''+str(arm)+'''" "'''+str(arm/'plm_writer.cpp')+'''" -lcrypto -o "'''+str(w/'libplm_writer_a53.so')+'''"
''');run(['bash',script],'CONTROL_ARM_BUILD-v1',w)
    b=read(OUT/'BUILD-v1.json');b.update(adapter=str(lib),writer_library=str(writer),writer_sha256=sha(writer),resident_request_limit=9)
    b['runtime_artifacts']=[dict(row,path=str(lib),sha256=sha(lib),bytes=lib.stat().st_size) if row['role']=='adapter' else row for row in b['runtime_artifacts']]
    save(OUT/'BUILD-v2.json',b)
    artifacts=[lib,writer,w/'liba12_resident_unbound.so',w/'liba12_resident_bound_candidate.so',w/'libplm_writer_a53.so']
    save(OUT/'CONTROL_BUILD-v1.json',dict(status='PC_CONTROL_AND_A53_CANDIDATES_COMPILED_ONLY',artifacts=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in artifacts],
        private_request_limit=9,old_control_artifacts_unchanged=True,math_recompiled=False,ARM_execution='NOT_EXECUTED',BOARD='NOT_TESTED',production_enabled=False))
    print('PC_CONTROL_AND_A53_NINE_REQUEST_CANDIDATES_BUILT')
if __name__=='__main__':main()
