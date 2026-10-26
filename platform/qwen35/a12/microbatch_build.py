"""Generate a minimal derivative of the frozen PC adapter, then build locally."""
import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
from microbatch_evidence import ROOT,OUT,WORK,read,save,sha,pin

PARENT_SHA='c4f4421a3f923793633e192dcdb6d7b516bdbe925a2ff83bf2008931253a9c1b'


def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,default=1)
    p.add_argument('--review-existing',type=int);a=p.parse_args()
    if a.review_existing:
        receipt=OUT/('BUILD-v'+str(a.review_existing)+'.json');r=read(receipt);source=Path(r['workspace'])/'source'
        assert r['exit_code']==0 and sha(r['library'])==r['library_sha256']
        assert all(sha(source/x['name'])==x['sha256'] for x in r['source'])
        r['legacy_parent_source_sha256']=r['source_sha256']
        r['source_sha256']=sha(source/'native_cpu_microbatch.cpp');r['raw_build_receipt_sha256']=sha(receipt)
        r['metadata_review']='Legacy parent source_sha256 corrected; raw build and binary untouched'
        save(OUT/('BUILD-v'+str(a.review_existing)+'-reviewed.json'),r);return
    assert os.name=='posix' and platform.machine()=='x86_64' and 1<=a.revision<=9
    work=WORK.with_name(WORK.name[:-1]+str(a.revision));os.umask(0o077);work.mkdir(mode=0o700,exist_ok=False)
    source=work/'source';source.mkdir();parent=ROOT/'platform/qwen35/a12/native_cpu_control.cpp'
    assert sha(parent)==PARENT_SHA
    text=parent.read_text();start=text.index('struct Control {');end=text.index('\n};\n}',start)+4
    text=text[:start]+'using Control=mb::Control;'+text[end:]
    substitutions=[
        ('using json=nlohmann::json;','using json=nlohmann::json;\n#include "microbatch_guard.hpp"'),
        ('r["pc_adapter"]="A12_NATIVE_CPU_CONTROL_V1"','r["pc_batch"]=control.report();r["pc_adapter"]="A12_NATIVE_CPU_MICROBATCH_V1"'),
        ('cfg.at("schema")=="A12_NATIVE_CPU_CONTROL_V1"','cfg.at("schema")=="A12_NATIVE_CPU_MICROBATCH_V1"'),
        ('auto c=std::make_unique<sp_linear_context>();','auto c=std::make_unique<sp_linear_context>();c->control.configure(cfg);'),
        ('c->control.permit("submit",job);++c->started;','c->control.before(job,t);++c->started;'),
        ('++c->verified;c->last_job=job;','c->control.after(job);++c->verified;c->last_job=job;')]
    for old,new in substitutions:assert text.count(old)==1,old;text=text.replace(old,new)
    (source/'native_cpu_microbatch.cpp').write_text(text)
    for name,path in [('microbatch_guard.hpp',ROOT/'platform/qwen35/a12/microbatch_guard.hpp'),
            ('sp_linear_v1.h',ROOT/'contracts/qwen35/sp_linear_v1.h'),
            ('prefix_cache.hpp',ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1/source-04/prefix_cache.hpp')]:shutil.copyfile(path,source/name)
    prior=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json')
    old=read(ROOT/'evidence/model_pl_A/20261026-native-request-journal-v1/BUILD-v2.json')
    include=Path(prior['workspace'])/'llama-source/vendor/nlohmann';lib=work/'liba12_native_cpu_control.so'
    argv=['g++','-std=c++17','-O2','-fPIC','-shared','-fvisibility=hidden','-DSP_A12_PC_TEST=1',
        '-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-I'+str(source),'-I'+str(include),
        str(source/'native_cpu_microbatch.cpp'),'-o',str(lib),'-ldl','-l:libcrypto.so.3']
    run=subprocess.run(argv,capture_output=True,text=True)
    (OUT/('build-'+str(a.revision)+'.stdout')).write_text(run.stdout);(OUT/('build-'+str(a.revision)+'.stderr')).write_text(run.stderr)
    r=dict(old,status='PASS_PC_ADAPTER_BUILD' if run.returncode==0 else 'FAIL_PC_ADAPTER_BUILD',
        workspace=str(work),library=str(lib),command=argv,exit_code=run.returncode,
        source=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(source.iterdir())],
        original_adapter_sha256=PARENT_SHA,revision=a.revision,PC_only=True,BOARD='NOT_TESTED',
        local_budget_requires_trusted_worker=True)
    r['source_sha256']=sha(source/'native_cpu_microbatch.cpp')
    for path,key in [(old['existing_native'],'existing_native_sha256'),(old['existing_cpu_library'],'existing_cpu_library_sha256')]:assert sha(path)==old[key]
    if run.returncode==0:r['library_sha256']=sha(lib)
    else:r.pop('library_sha256',None)
    save(OUT/('BUILD-v'+str(a.revision)+'.json'),r);print(run.stderr);raise SystemExit(run.returncode)

if __name__=='__main__':main()
