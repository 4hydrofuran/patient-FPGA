"""Reuse the actual frozen front/math; compile the generation consumer only."""
import argparse
import copy
import os
from pathlib import Path
import shutil
import subprocess
from generation_evidence import ROOT,OUT,PARENT,WORK,read,save,sha
from modelpl_derive import Derive

def run(argv,label,cwd,timeout=180):
    r=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,text=True,timeout=timeout)
    save(OUT/(label+'.json'),dict(command=[str(x) for x in argv],cwd=str(cwd),exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
    print(label,r.returncode,flush=True)
    if r.returncode:print(r.stderr[-2500:]);raise SystemExit(r.returncode)
    return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);a=p.parse_args()
    assert os.name=='posix' and 1<=a.revision<=9;os.umask(0o077)
    work=WORK.with_name(WORK.name[:-1]+str(a.revision));work.mkdir(mode=0o700);src=work/'source';src.mkdir()
    b=read(PARENT/'BUILD-v5.json');old=Path(b['workspace'])/'source'
    for row in b['source']:assert sha(old/row['name'])==row['sha256']
    for row in b['source']:
        if row['name'].endswith(('.h','.hpp')):shutil.copyfile(old/row['name'],src/row['name'])
    here=ROOT/'platform/qwen35/a12'
    for name in ('generation_slot.hpp','generation_writer.cpp','test_generation_slot.cpp'):shutil.copyfile(here/name,src/name)
    d=Derive((old/'modelpl_cpu.cpp').read_text());d.edit('#include "plm_control.hpp"','#include "generation_slot.hpp"')
    d.edit('plm::Control authority;','generation::Control<generation::PC_FIXTURE> authority;')
    cpu,changes=d.finish();(src/'generation_cpu.cpp').write_text(cpu)
    save(OUT/f'SOURCE-v{a.revision}.json',dict(workspace=str(work),source=[dict(name=p.name,sha256=sha(p),bytes=p.stat().st_size) for p in sorted(src.iterdir())],
        CPU_adapter_reversible_edits=changes,original_CPU_adapter_sha256=sha(old/'modelpl_cpu.cpp'),BOARD='NOT_TESTED'))
    ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root')
    flags=['g++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-I'+str(src),
        '-I'+str(ssl/'usr/include'),'-I'+str(ssl/'usr/include/x86_64-linux-gnu')]
    adapter=work/'liba12_native_cpu_control.so';writer=work/'liba12_generation_writer.so'
    run(flags+['-shared','-fPIC','-fvisibility=hidden','-DSP_A12_PC_TEST=1',src/'generation_cpu.cpp','-o',adapter,'-ldl','-l:libcrypto.so.3'],'CPU_ADAPTER-v'+str(a.revision),work)
    exports=src/'generation.map';exports.write_text('{ global: a12_gen_*_v1; local: *; };\n')
    run(flags+['-shared','-fPIC','-fvisibility=hidden',src/'generation_writer.cpp','-o',writer,'-Wl,--version-script='+str(exports),'-l:libcrypto.so.3'],'SLOT_WRITER-v'+str(a.revision),work)
    test=work/'test-generation-slot';run(flags+[src/'test_generation_slot.cpp','-o',test,'-l:libcrypto.so.3'],'SLOT_TEST_BUILD-v'+str(a.revision),work)
    run([test],'SLOT_TEST-v'+str(a.revision),work)
    san=work/'test-generation-slot-san'
    run(flags+['-fsanitize=address,undefined','-fno-omit-frame-pointer',src/'test_generation_slot.cpp','-o',san,'-l:libcrypto.so.3'],'SLOT_SAN_BUILD-v'+str(a.revision),work)
    run([san],'SLOT_SAN-v'+str(a.revision),work)
    new=copy.deepcopy(b);new.update(workspace=str(work),revision=a.revision,adapter=str(adapter),generation_writer=str(writer),generation_writer_sha256=sha(writer),
        native_reused_unchanged=True,real_device_generation_approval='UNBOUND_NO_BOARD_ISSUER',generation_domain='PC_GENERATION_FIXTURE_NO_DEVICE')
    for row in new['runtime_artifacts']:
        if row['role']=='adapter':row.update(path=str(adapter),sha256=sha(adapter),bytes=adapter.stat().st_size)
        else:assert sha(row['path'])==row['sha256']
    new['generation_source']=[dict(name=p.name,sha256=sha(p),bytes=p.stat().st_size) for p in sorted(src.iterdir())]
    save(OUT/f'BUILD-v{a.revision}.json',new)
    print('PASS_GENERATION_PC_BUILD')
if __name__=='__main__':main()
