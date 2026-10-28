"""Rebuild ONLY private front/Route/adapters; reuse pinned quant object and math DSOs."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from modelpl_evidence import ROOT,OUT,WORK,BUNDLE,PARENT,read,save,sha
from modelpl_derive import runtime,cpu
from plm_derive import generate as pl_backend

def run(argv,label,cwd,timeout=180):
    r=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,text=True,timeout=timeout)
    save(OUT/(label+'.json'),dict(command=[str(x) for x in argv],cwd=str(cwd),exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
    print(label,r.returncode,flush=True)
    if r.returncode:print(r.stderr[-5000:]);raise SystemExit(r.returncode)
    return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);a=p.parse_args();assert os.name=='posix' and 1<=a.revision<=9
    work=WORK.with_name(WORK.name[:-1]+str(a.revision));os.umask(0o077);work.mkdir(mode=0o700);src=work/'source';src.mkdir();cmake=work/'cmake';cmake.mkdir()
    outputs,changes=runtime();manifest=read(BUNDLE/'manifest.json');pins={r['path']:r for r in manifest['files']}
    for name in ('main.cpp','bridge.cpp','bridge.hpp','route.cpp','route.hpp','request_profile.cpp','request_profile.hpp','prefix_cache.hpp','diagnostic_io.hpp','sp-hook.h'):
        original=BUNDLE/'source'/name;assert sha(original)==pins['source/'+name]['sha256']
        if name in outputs:(src/name).write_text(outputs[name])
        else:shutil.copyfile(original,src/name)
    shutil.copyfile(BUNDLE/'source/supervisor_gate.hpp',src/'supervisor_gate.hpp')
    parent=read(PARENT/'BUILD-v4.json');old=Path(parent['workspace'])/'source'
    for name in ('plm_control.hpp','plm_page.hpp','pl_auth_gate.hpp','json.hpp','sp_linear_v1.h'):
        shutil.copyfile(old/name,src/name)
    adapter,adapter_changes=cpu();(src/'modelpl_cpu.cpp').write_text(adapter)
    old_native=Path('/home/member-a/kv260-build/a12-tt10-01-20261024-v1')
    # Import the already executed quantization object, rather than recompiling mathematics.
    objects=list((old_native/'pc04/CMakeFiles').rglob('w4a8.cpp.o'));assert len(objects)==1
    quant_object=objects[0];cmake_text=(old_native/'cmake/CMakeLists.txt').read_text()
    assert cmake_text.count('${ROOT}/quant/reference/w4a8.cpp')==1
    cmake_text=cmake_text.replace('${ROOT}/quant/reference/w4a8.cpp','${EXISTING_QUANT_OBJECT}')
    (cmake/'CMakeLists.txt').write_text(cmake_text)
    first=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json');second=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json')
    old_prefix=read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02/prefix-config-PC.json')
    base=Path(second['workspace'])/'pc';cpu_lib=base/'libsp_linear_cpu.so';assert sha(cpu_lib)==old_prefix['identity']['libraries']['libsp_linear_cpu.so']
    llama=Path(first['workspace'])/'pc-llama';llama_source=Path(first['workspace'])/'llama-source'
    math_files=[cpu_lib]+[llama/'bin'/name for name in ('libllama.so','libggml.so','libggml-base.so','libggml-cpu.so')]
    math_before=[dict(path=str(p.resolve()),sha256=sha(p),bytes=p.stat().st_size) for p in math_files]
    save(OUT/f'SOURCE_SNAPSHOT-v{a.revision}.json',dict(workspace=str(work),source=[dict(name=p.name,sha256=sha(p),bytes=p.stat().st_size) for p in sorted(src.iterdir())],
        frontend_derivation=changes,CPU_adapter_derivation=adapter_changes,math_libraries=math_before,imported_quant_object=dict(path=str(quant_object),sha256=sha(quant_object)),
        cmake_sha256=sha(cmake/'CMakeLists.txt'),BOARD='NOT_TESTED'))
    build=work/'pc';run(['cmake','-S',cmake,'-B',build,'-DCMAKE_BUILD_TYPE=Release','-DROOT='+str(ROOT),'-DA12_SOURCE='+str(src),
        '-DASSET_ROOT='+str(ROOT),'-DLLAMA_SOURCE='+str(llama_source),'-DLLAMA_BUILD='+str(llama),'-DBASE_BUILD='+str(base),
        '-DEXISTING_QUANT_OBJECT='+str(quant_object)],f'PC_CONFIGURE-v{a.revision}',work)
    run(['cmake','--build',build,'-j4'],f'PC_NATIVE_BUILD-v{a.revision}',work)
    library=work/'liba12_native_cpu_control.so'
    ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root')
    run(['g++','-std=c++17','-O2','-shared','-fPIC','-fvisibility=hidden','-DSP_A12_PC_TEST=1','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra',
        '-I'+str(src),'-I'+str(ssl/'usr/include'),'-I'+str(ssl/'usr/include/x86_64-linux-gnu'),
        str(src/'modelpl_cpu.cpp'),'-o',library,'-ldl','-l:libcrypto.so.3'],f'PC_ADAPTER_BUILD-v{a.revision}',work)
    for row in math_before:assert sha(row['path'])==row['sha256']
    native=build/'qwen35-a12';artifacts=[dict(role='native',path=str(native),sha256=sha(native),bytes=native.stat().st_size),
        dict(role='adapter',path=str(library),sha256=sha(library),bytes=library.stat().st_size)]+[dict(row,role='math_library') for row in math_before]
    save(OUT/f'BUILD-v{a.revision}.json',dict(domain='PC_REAL_MODEL_PLM_V1',workspace=str(work),revision=a.revision,native=str(native),adapter=str(library),
        CPU_library=str(cpu_lib),CPU_library_sha256=sha(cpu_lib),runtime_artifacts=artifacts,math_libraries_before_and_after=math_before,
        imported_quant_object=dict(path=str(quant_object),sha256=sha(quant_object)),quant_math_recompiled=False,math_DSO_recompiled=False,
        writer_library=parent['writer_library'],writer_sha256=parent['writer_sha256'],observer_library=read(PARENT/'OBSERVER_REVIEWED-v2.json')['library'],
        source=[dict(name=p.name,sha256=sha(p),bytes=p.stat().st_size) for p in sorted(src.iterdir())],
        frontend_derivation=changes,CPU_adapter_derivation=adapter_changes,BOARD='NOT_TESTED',production_enabled=False,real_device_generation_approval='UNBOUND'))
    print('PC_REAL_MODEL_FRONT_ROUTE_AND_ADAPTER_BUILD_PASS')
if __name__=='__main__':main()
