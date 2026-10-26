"""Build only the manager issuer; frozen native/CPU/XRT consumers are reused."""
import argparse
import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
from livegen_evidence import ROOT,OUT,PARENT,WORK,read,save,sha
from modelpl_derive import Derive

BOARD_OPEN=r'''
#include <sys/utsname.h>
GEN_API void* a12_livegen_board_open_v1(int fd,const char*id,const char*epoch){
#if defined(__aarch64__)
    try{
        generation::need(id&&epoch&&geteuid()==0);utsname u{};generation::need(!uname(&u)&&std::string(u.release)=="6.8.12-a10irq2");
        std::ifstream input("/etc/machine-id");char buffer[4097];input.read(buffer,sizeof buffer);auto count=input.gcount();
        generation::need(count>0&&count<=4096);std::string text(buffer,size_t(count));unsigned char bytes[32];unsigned n=0;uint64_t words[4];
        generation::need(EVP_Digest(text.data(),text.size(),bytes,&n,EVP_sha256(),nullptr)==1&&n==32);std::memcpy(words,bytes,32);
        generation::need(plm::hex(words)=="ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec");
        return new generation::Writer(fd,id,epoch,generation::BOARD);
    }catch(...){return nullptr;}
#else
    (void)fd;(void)id;(void)epoch;return nullptr; // PC has no positive Board issuer.
#endif
}
'''

def run(argv,label,cwd=ROOT,timeout=180):
    argv=[str(x) for x in argv];r=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=timeout)
    save(OUT/(label+'.json'),dict(command=argv,cwd=str(cwd),exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));print(label,r.returncode,flush=True)
    if r.returncode:print(r.stderr[-3000:]);raise SystemExit(r.returncode)
    return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);a=p.parse_args();assert os.name=='posix' and 1<=a.revision<=9
    os.umask(0o077);w=WORK.with_name(WORK.name[:-1]+str(a.revision));w.mkdir();src=w/'source';src.mkdir()
    old=read(PARENT/'BUILD-v3.json');previous=Path(old['workspace'])/'source'
    for row in old['generation_source']:
        assert sha(previous/row['name'])==row['sha256']
        if row['name'].endswith(('.hpp','.h')) or row['name'] in ('generation_writer.cpp','test_generation_slot.cpp'):
            shutil.copyfile(previous/row['name'],src/row['name'])
    d=Derive((src/'generation_slot.hpp').read_text())
    d.edit('Writer(int fd,const char*id,const char*epoch){','Writer(int fd,const char*id,const char*epoch,uint64_t requested_domain=PC_FIXTURE){')
    d.edit('s->domain=PC_FIXTURE; // There is deliberately NO Board-positive issuer.',
        'need(requested_domain==PC_FIXTURE||requested_domain==BOARD);s->domain=requested_domain; // issuer selects a compile/runtime fenced domain')
    d.edit('uint64_t zero=0;need(s->state.compare_exchange_strong(zero,LOADING));live(p,PC_FIXTURE,LOADING);}',
        'uint64_t zero=0;need(s->state.compare_exchange_strong(zero,LOADING));live(p,s->domain,LOADING);}')
    d.edit('void resident(const char*sha){auto s=slot(p);auto h=plm::words(sha);live(p,PC_FIXTURE,LOADING);',
        'void resident(const char*sha){auto s=slot(p);auto h=plm::words(sha);live(p,s->domain,LOADING);')
    header,changes=d.finish();(src/'generation_slot.hpp').write_text(header)
    original=(src/'generation_writer.cpp').read_text();(src/'generation_writer.cpp').write_text(original+BOARD_OPEN)
    exports=src/'exports.map';exports.write_text('{ global: a12_gen_*_v1; a12_livegen_board_open_v1; local: *; };\n')
    save(OUT/f'SOURCE-v{a.revision}.json',dict(header_reversible_edits=changes,writer_append=BOARD_OPEN,
        original_header_sha256=sha(previous/'generation_slot.hpp'),original_writer_sha256=sha(previous/'generation_writer.cpp'),
        source=[dict(name=p.name,sha256=sha(p)) for p in sorted(src.iterdir())]))
    ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root')
    flags=['g++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-I'+str(src),
        '-I'+str(ssl/'usr/include'),'-I'+str(ssl/'usr/include/x86_64-linux-gnu')]
    writer=w/'liba12_livegen_writer.so';run(flags+['-shared','-fPIC','-fvisibility=hidden',src/'generation_writer.cpp','-Wl,--version-script='+str(exports),'-o',writer,'-l:libcrypto.so.3'],f'PC_WRITER-v{a.revision}',w)
    test=w/'test-generation-slot';run(flags+[src/'test_generation_slot.cpp','-o',test,'-l:libcrypto.so.3'],f'NATIVE_TEST_BUILD-v{a.revision}',w);run([test],f'NATIVE_TEST-v{a.revision}',w)
    san=w/'test-generation-slot-san';run(flags+['-fsanitize=address,undefined','-fno-omit-frame-pointer',src/'test_generation_slot.cpp','-o',san,'-l:libcrypto.so.3'],f'NATIVE_SAN_BUILD-v{a.revision}',w);run([san],f'NATIVE_SAN-v{a.revision}',w)
    arm=w/'liba12_livegen_writer_a53.so';script=w/'build-arm-issuer.sh'
    script.write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
test "$OECORE_SDK_VERSION" = 2026.1
set -x
aarch64-amd-linux-g++ --sysroot="$SDKTARGETSYSROOT" -mcpu=cortex-a53 -O2 -std=c++17 -shared -fPIC -fvisibility=hidden -fno-fast-math -ffp-contract=off -Wall -Wextra -I"'''+str(src)+'''" "'''+str(src/'generation_writer.cpp')+'''" -Wl,--version-script="'''+str(exports)+'''" -Wl,-z,defs -lcrypto -pthread -o "'''+str(arm)+'''"
readelf -h -d --dyn-syms --wide "'''+str(arm)+'''"
''')
    run(['bash',script],f'A53_WRITER-v{a.revision}',w)
    for row in old['runtime_artifacts']:assert sha(row['path'])==row['sha256']
    new=copy.deepcopy(old);observer=read(ROOT/'evidence/model_pl_A/20261026-pl-manager-v1/OBSERVER_REVIEWED-v2.json')
    assert sha(observer['library'])==observer['sha256']
    new.update(workspace=str(w),generation_writer=str(writer),generation_writer_sha256=sha(writer),observer_sha256=observer['sha256'],
        source_binding='LIVE_OWNER_PORTS_IMPLEMENTED_PC_FIXTURE_TESTS_NOT_BOARD_VALIDATED',real_device_generation_approval='UNBOUND_CURRENT_BOARD_WINDOW',
        manager_artifacts=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in (writer,arm)],ARM_execution='NOT_EXECUTED',BOARD='NOT_TESTED')
    save(OUT/f'BUILD-v{a.revision}.json',new);print('PASS_LIVE_SOURCE_MANAGER_ISSUER_PC_A53_COMPILE_ONLY')
if __name__=='__main__':main()
