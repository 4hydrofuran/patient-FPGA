"""Reproducible A-owned private A12 derivative, original received B core unchanged."""
import argparse
import json
from pathlib import Path
import shutil
from common import ROOT, sha, save


def derive(out):
    out=Path(out);out.mkdir(exist_ok=False,parents=True)
    source=ROOT/'evidence/mlp_board_A/20261023-open-investigation-v1/bo-diagnostics-v1/derived/backend.cpp'
    if sha(source)!='e5a27149747f3ee804d4c46c5ceb7b4eef08132058be1264d1351cc29429e093':
        raise ValueError('A11 source hash differs')
    text=source.read_text()
    def replace(old,new):
        nonlocal text
        if text.count(old)!=1:raise ValueError('nonunique derivative context: '+old[:80])
        text=text.replace(old,new)
    replace('#include "managed_lock.hpp"','#include "managed_lock.hpp"\n#include "supervisor_gate.hpp"')
    replace('uint64_t next=1,budget=0,used=0,align=0,loads=0,runs=0;',
            'uint64_t next=1,budget=0,used=0,align=0,loads=0,runs=0,max_runs=0,max_loads=0;')
    replace('A11_BOUNDED_TRIAL_AUTHORIZED_NOT_ACCEPTED','A12_BOUNDED_MODEL_TRIAL_NOT_ACCEPTED')
    replace('number(profile,"trial_bo_limit_bytes",4ULL*1024*1024)',
            'number(profile,"trial_bo_limit_bytes",256ULL*1024*1024)')
    replace('    require(c->budget&&c->align&&!(c->align&(c->align-1)),SP_UNSUPPORTED);', '''
    require(c->budget&&c->align==8192,SP_UNSUPPORTED);
    c->max_runs=number(profile,"a12_max_runs",65536);
    c->max_loads=number(profile,"a12_max_loads",72);
    require(c->max_runs&&c->max_loads,SP_UNSUPPORTED);
    a12::permit("device_open",0);''')
    replace('    uint64_t amount=charge(a.w,c->align)+charge(a.sw,c->align);', '''
    if(c->loads>=c->max_loads)return SP_UNSUPPORTED;
    a12::permit("weight_load",c->loads+1);
    uint64_t amount=charge(a.w,c->align)+charge(a.sw,c->align);''')
    replace('    if(c->runs>=23)return SP_UNSUPPORTED;', '''
    if(c->runs>=c->max_runs)return SP_UNSUPPORTED;
    a12::permit("submit",job);''')
    replace('j["candidate_scope"]="A11_BOUNDED_MAINTENANCE_NOT_DEFAULT_DEPLOYMENT";', '''
    j["candidate_scope"]="A12_BOUNDED_MODEL_TRIAL_NOT_DEFAULT";
    j["a12_max_runs"]=c->max_runs;j["a12_max_loads"]=c->max_loads;
    j["a12_hardware_global_completion_counter"]=nullptr;''')
    (out/'backend.cpp').write_text(text,encoding='utf-8')
    for name in ('main.cpp','bridge.cpp','bridge.hpp','sp-hook.cpp','sp-hook.h',
                 'request_profile.hpp','request_profile.cpp'):
        shutil.copyfile(ROOT/'runtime/qwen35_w4a8'/name,out/name)
    save(out/'DERIVATION.json',dict(provider='B',maintainer='A',source_sha256=sha(source),
        derived_sha256=sha(out/'backend.cpp'),contract_changed=False,math_changed=False,
        B_core_changed=False,BOARD='NOT_TESTED',
        changes=['8192 mandatory','profile bounds run/load/BO','parent permit before open/load/run',
                 '72 resident handles via existing map; no per-token weight upload']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    derive(p.parse_args().out)
