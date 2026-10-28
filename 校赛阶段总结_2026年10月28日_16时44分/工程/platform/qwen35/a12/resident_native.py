"""Only native glue adds a bounded vocab-only branch before private op denial."""
import os
from pathlib import Path
import shutil
import subprocess
from resident_evidence import ROOT,OUT,WORK,read,save,sha
from modelpl_derive import Derive

TOKENIZE=r'''        if(bridge.route.private_control&&op=="tokenize"){
            auto state=bridge.route.private_status();
            if(state.at("enabled")!=true||state.at("request_active")!=false||state.at("failed")!=false||state.at("closed")!=false)
                throw std::runtime_error("private vocab-only operation requires healthy idle native route");
            if(req.size()!=3||!req.contains("prompt")||!req.at("prompt").is_string()||!req.contains("id")||!req.at("id").is_string())
                throw std::runtime_error("private vocab-only request fields");
            if(id.empty()||id.size()>48)throw std::runtime_error("private vocab-only ID bound");
            for(char c:id)if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'))
                throw std::runtime_error("private vocab-only ID syntax");
            std::string prompt=req.at("prompt");if(prompt.empty()||prompt.size()>4096)throw std::runtime_error("private vocab-only prompt bound");
            int n=llama_tokenize(vocab,prompt.data(),prompt.size(),nullptr,0,true,true);
            if(n>=0||n<-128)throw std::runtime_error("private vocab-only token bound");
            std::vector<llama_token> tokens(size_t(-n));n=llama_tokenize(vocab,prompt.data(),prompt.size(),tokens.data(),tokens.size(),true,true);
            if(n<=0||n>128)throw std::runtime_error("private vocab-only tokenization");tokens.resize(n);
            emit({{"type","tokens"},{"id",id},{"tokens",tokens},{"domain",bridge.route.real?"BOARD":"PC"},
                {"execution_kind","VOCAB_ONLY_NO_BACKEND_CALL"},{"private_control",state}});continue;
        }
'''

def run(cmd,label,cwd=ROOT,timeout=240):
    cmd=[str(x) for x in cmd];r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=timeout)
    save(OUT/(label+'.json'),dict(command=cmd,cwd=str(cwd),exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));print(label,r.returncode,flush=True)
    if r.returncode:print(r.stderr[-3000:]);raise SystemExit(r.returncode)

def main():
    assert os.name=='posix';os.umask(0o077);WORK.mkdir();src=WORK/'source';src.mkdir();cmake=WORK/'cmake';cmake.mkdir()
    old=read(ROOT/'evidence/model_pl_A/20261026-model-route-v1/BUILD-v5.json');original=Path(old['workspace'])
    for row in old['source']:
        p=original/'source'/row['name'];assert sha(p)==row['sha256'];shutil.copyfile(p,src/row['name'])
    d=Derive((src/'main.cpp').read_text());guard='        if(bridge.route.private_control&&op!="generate"&&op!="cache_create")throw std::runtime_error("private control forbids auxiliary compute/cache operations");'
    d.edit(guard,TOKENIZE+guard);main_text,edits=d.finish();(src/'main.cpp').write_text(main_text)
    shutil.copyfile(original/'cmake/CMakeLists.txt',cmake/'CMakeLists.txt')
    first=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json');second=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json')
    root_first=Path(first['workspace']);base=Path(second['workspace']);quant=old['imported_quant_object'];assert sha(quant['path'])==quant['sha256']
    math=old['math_libraries_before_and_after']
    for row in math:assert sha(row['path'])==row['sha256']
    save(OUT/'NATIVE_SOURCE-v1.json',dict(main_reversible_edits=edits,original_main_sha256=next(r['sha256'] for r in old['source'] if r['name']=='main.cpp'),
        source=[dict(name=p.name,sha256=sha(p)) for p in sorted(src.iterdir())],math_libraries=math,imported_quant_object=quant,
        separate_tokenizer_model_created=False,extra_CMA_BOs=0,ARM_execution='NOT_EXECUTED'))
    run(['cmake','-S',cmake,'-B',WORK/'pc','-DCMAKE_BUILD_TYPE=Release','-DROOT='+str(ROOT),'-DA12_SOURCE='+str(src),'-DASSET_ROOT='+str(ROOT),
        '-DLLAMA_SOURCE='+str(root_first/'llama-source'),'-DLLAMA_BUILD='+str(root_first/'pc-llama'),'-DBASE_BUILD='+str(base/'pc'),'-DEXISTING_QUANT_OBJECT='+quant['path']], 'PC_CONFIGURE-v1')
    run(['cmake','--build',WORK/'pc','-j4'],'PC_NATIVE_BUILD-v1',WORK)
    arm_old=read(ROOT/'evidence/model_pl_A/20261026-model-route-v1/ARM_BUILD-v5.json');arm_quant=next(r for r in arm_old['original_math_before_and_after'] if r['path'].endswith('.o'))
    script=WORK/'build-arm.sh';script.write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/member-a/kv260-sdk-2026.1-common/environment-setup-cortexa72-cortexa53-amd-linux
test "$OECORE_SDK_VERSION" = 2026.1
export CC=aarch64-amd-linux-gcc CXX=aarch64-amd-linux-g++
export CFLAGS="--sysroot=$SDKTARGETSYSROOT -mcpu=cortex-a53 -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2"
export CXXFLAGS="$CFLAGS" CPPFLAGS=""
cmake -S "'''+str(cmake)+'''" -B "'''+str(WORK/'arm')+'''" -DCMAKE_TOOLCHAIN_FILE="$OECORE_NATIVE_SYSROOT/usr/share/cmake/OEToolchainConfig.cmake" -DCMAKE_BUILD_TYPE=Release -DROOT=/mnt/c/Patientqwen -DA12_SOURCE="'''+str(src)+'''" -DASSET_ROOT=/opt/patient-qwen -DLLAMA_SOURCE="'''+str(root_first/'llama-source')+'''" -DLLAMA_BUILD="'''+str(root_first/'arm-llama')+'''" -DBASE_BUILD="'''+str(base/'model')+'''" -DEXISTING_QUANT_OBJECT="'''+arm_quant['path']+'''"
cmake --build "'''+str(WORK/'arm')+'''" -j4
''')
    run(['bash',script],'ARM_NATIVE_BUILD-v1',WORK)
    for row in math+arm_old['original_math_before_and_after']+[quant]:assert sha(row['path'])==row['sha256']
    pc=WORK/'pc/qwen35-a12';arm=WORK/'arm/qwen35-a12'
    build=read(ROOT/'evidence/model_pl_A/20261026-pl-mode-v1/BUILD-v2.json');build.update(workspace=str(WORK),native=str(pc))
    build['runtime_artifacts']=[dict(row,path=str(pc),sha256=sha(pc),bytes=pc.stat().st_size) if row['role']=='native' else row for row in build['runtime_artifacts']]
    save(OUT/'BUILD-v1.json',build)
    save(OUT/'NATIVE_REVIEW-v1.json',dict(status='PC_AND_A53_GLUE_BUILT_VOCAB_ONLY_BRANCH_NOT_ARM_EXECUTED',
        PC=dict(path=str(pc),sha256=sha(pc)),A53=dict(path=str(arm),sha256=sha(arm)),math_recompiled=False,
        native_glue_recompiled=True,ARM_execution='NOT_EXECUTED',BOARD='NOT_TESTED',production_enabled=False))
    print('PC_AND_A53_BOUNDED_VOCAB_ONLY_GLUE_BUILT')
if __name__=='__main__':main()
