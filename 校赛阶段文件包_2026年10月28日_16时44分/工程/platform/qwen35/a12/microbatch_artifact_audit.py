"""Verify built derivative, inverse patch, ELF and unchanged native/CPU artifacts."""
import subprocess
from pathlib import Path
from microbatch_evidence import ROOT,OUT,read,save,sha

build=read(OUT/'BUILD-v5-reviewed.json');source=Path(build['workspace'])/'source'
assert build['exit_code']==0 and sha(build['library'])==build['library_sha256']
assert all(sha(source/r['name'])==r['sha256'] for r in build['source'])
assert sha(source/'microbatch_guard.hpp')==sha(ROOT/'platform/qwen35/a12/microbatch_guard.hpp')
assert sha(source/'native_cpu_microbatch.cpp')==build['source_sha256']
assert sha(build['existing_native'])==build['existing_native_sha256']
assert sha(build['existing_cpu_library'])==build['existing_cpu_library_sha256']
parent=ROOT/'platform/qwen35/a12/native_cpu_control.cpp';assert sha(parent)==build['original_adapter_sha256']
text=(source/'native_cpu_microbatch.cpp').read_text();original=parent.read_text()
changes=[
    ('using json=nlohmann::json;','using json=nlohmann::json;\n#include "microbatch_guard.hpp"'),
    ('r["pc_adapter"]="A12_NATIVE_CPU_CONTROL_V1"','r["pc_batch"]=control.report();r["pc_adapter"]="A12_NATIVE_CPU_MICROBATCH_V1"'),
    ('cfg.at("schema")=="A12_NATIVE_CPU_CONTROL_V1"','cfg.at("schema")=="A12_NATIVE_CPU_MICROBATCH_V1"'),
    ('auto c=std::make_unique<sp_linear_context>();','auto c=std::make_unique<sp_linear_context>();c->control.configure(cfg);'),
    ('c->control.permit("submit",job);++c->started;','c->control.before(job,t);++c->started;'),
    ('++c->verified;c->last_job=job;','c->control.after(job);++c->verified;c->last_job=job;')]
for old,new in changes:assert text.count(new)==1;text=text.replace(new,old)
start=original.index('struct Control {');end=original.index('\n};\n}',start)+4
assert text.count('using Control=mb::Control;')==1
text=text.replace('using Control=mb::Control;',original[start:end]);assert text==original
commands=[]
for name,argv in [('elf',['readelf','-h','-d',build['library']]),('symbols',['nm','-D','--defined-only',build['library']])]:
    r=subprocess.run(argv,capture_output=True,text=True);assert r.returncode==0
    (OUT/(name+'.txt')).write_text(r.stdout);commands.append(dict(command=argv,exit_code=r.returncode))
elf=(OUT/'elf.txt').read_text();symbols=(OUT/'symbols.txt').read_text()
assert 'X86-64' in elf and 'libxrt' not in elf.lower()
for name in ('open','load','run','report','unload','close'):assert ' sp_linear_'+name+'_v1' in symbols
save(OUT/'ARTIFACT_AUDIT.json',dict(status='PASS_PC_ELF_INVERSE_PATCH_AND_PINNED_INPUTS',commands=commands,
    original_adapter_normalized_bytes_restored_exactly=True,CPU_math_rebuilt=False,native_executable_rebuilt=False,
    library_sha256=build['library_sha256'],generated_source_sha256=build['source_sha256'],
    private_header_sha256=sha(source/'microbatch_guard.hpp'),public_header_sha256=sha(source/'sp_linear_v1.h'),
    existing_CPU_sha256=build['existing_cpu_library_sha256'],existing_native_sha256=build['existing_native_sha256'],
    ARM_build='NOT_PERFORMED',BOARD='NOT_TESTED',XRT_link_dependency=False))
