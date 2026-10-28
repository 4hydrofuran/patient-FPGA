"""Build only the PC permit adapter using the existing compiler and CPU library."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261026-native-request-journal-v1'
WORK=Path('/home/member-a/kv260-build/a12-native-request-journal-20261026-v1')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,value):
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,default=1);args=p.parse_args()
    assert 1<=args.revision<=9
    work=WORK if args.revision==1 else WORK.with_name(WORK.name[:-1]+str(args.revision))
    assert os.name=='posix' and platform.machine().lower() in ('x86_64','amd64')
    os.umask(0o077);OUT.mkdir(parents=True,exist_ok=True);work.mkdir(exist_ok=False,parents=True,mode=0o700)
    source=work/'source';source.mkdir()
    shutil.copyfile(ROOT/'platform/qwen35/a12/native_cpu_control.cpp',source/'native_cpu_control.cpp')
    parent=ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1/source-04/prefix_cache.hpp'
    shutil.copyfile(parent,source/'prefix_cache.hpp')
    shutil.copyfile(ROOT/'contracts/qwen35/sp_linear_v1.h',source/'sp_linear_v1.h')
    prior=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json')
    prior2=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json')
    native=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02/RESULT.json'
    cpu=Path(prior2['workspace'])/'pc/libsp_linear_cpu.so'
    assert sha(cpu)==read(native)['libraries']['libsp_linear_cpu.so']
    binary=Path('/home/member-a/kv260-build/a12-tt10-01-20261024-v1/pc04/qwen35-a12')
    assert sha(binary)==read(native)['native_sha256']
    include=Path(prior['workspace'])/'llama-source/vendor/nlohmann'
    library=work/'liba12_native_cpu_control.so'
    argv=['g++','-std=c++17','-O2','-fPIC','-shared','-fvisibility=hidden','-DSP_A12_PC_TEST=1',
          '-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-I'+str(source),'-I'+str(include),
          str(source/'native_cpu_control.cpp'),'-o',str(library),'-ldl','-l:libcrypto.so.3']
    run=subprocess.run(argv,capture_output=True,text=True)
    suffix='' if args.revision==1 else '-v'+str(args.revision)
    (OUT/('build-stdout'+suffix+'.txt')).write_text(run.stdout);(OUT/('build-stderr'+suffix+'.txt')).write_text(run.stderr)
    report=dict(status='PASS_PC_ADAPTER_BUILD' if run.returncode==0 else 'FAIL_PC_ADAPTER_BUILD',
        command=argv,exit_code=run.returncode,workspace=str(work),library=str(library),revision=args.revision,
        source_sha256=sha(source/'native_cpu_control.cpp'),public_header_sha256=sha(source/'sp_linear_v1.h'),
        existing_native=str(binary),existing_native_sha256=sha(binary),existing_cpu_library=str(cpu),
        existing_cpu_library_sha256=sha(cpu),native_executable_rebuilt=False,CPU_math_rebuilt=False,
        ARM_build='NOT_PERFORMED_PC_ONLY_SOURCE',BOARD='NOT_TESTED')
    if run.returncode==0:report['library_sha256']=sha(library)
    save(OUT/('BUILD'+suffix+'.json'),report);print(json.dumps(report,indent=2));raise SystemExit(run.returncode)


if __name__=='__main__':main()
