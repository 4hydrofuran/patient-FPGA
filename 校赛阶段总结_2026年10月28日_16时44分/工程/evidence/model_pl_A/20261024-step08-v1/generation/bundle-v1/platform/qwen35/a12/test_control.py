"""A12 XRT-control fault matrix; fake XRT never contributes numerical/board claims."""
import argparse
import json
from pathlib import Path
from common import ROOT, command, save


def main(source,out):
    out.mkdir(exist_ok=False,parents=True)
    a07=ROOT/'platform/qwen35/a07/control'
    runner=(a07/'run_cases.py').read_text()
    runner=runner.replace("cases=['gates'","cases=['a12_limit','a12_resident','gates'")
    runner=runner.replace("'verified_bo_budget_bytes':10000000,'bo_charge_alignment':4096",
                          "'trial_bo_limit_bytes':4194304,'bo_charge_alignment':8192,'a12_max_runs':24,'a12_max_loads':72")
    (out/'run_cases.py').write_text(runner)
    test=(a07/'test_api.cpp').read_text()
    anchor='        }else if(mode=="concurrency"){'
    assert test.count(anchor)==1
    test=test.replace(anchor,'''        }else if(mode=="a12_limit"){
            for(unsigned j=1;j<=24;++j)check(run(j)==0,"A12 crosses old 23-call limit with reviewed bound");
            check(run(25)==SP_UNSUPPORTED&&control::starts==24,"25th refused before transport");
            check(control::allocations==allocs,"24 calls use persistent IO and weights");
            check(control::count("to_5")==to_w&&control::count("to_3")==to_sw,"no repeated upload");
            auto r=report(c);check(r["a12_max_runs"]==24&&r["output_consumable"]==false,"new bound and invalidated output");
        }else if(mode=="a12_resident"){
            std::fill(w.begin(),w.end(),0);sw.assign(32,1);std::vector<uint64_t>hs;
            for(int i=0;i<71;++i){uint64_t h=0;check(sp_linear_load_v1(c,2,2,w.data(),w.size(),sw.data(),128,&h)==0,"72 resident handles");hs.push_back(h);}
            uint64_t h=0;auto before=control::allocations;
            check(sp_linear_load_v1(c,2,2,w.data(),w.size(),sw.data(),128,&h)==SP_UNSUPPORTED&&!h,"73rd load rejected");
            check(control::allocations==before,"load cap precedes allocation");
            auto r=report(c);check(r["weight_load_count"]==72,"truthful residency counter");
            check(run()==0,"first handle remains valid after all loads");
            for(auto h:hs)check(sp_linear_unload_v1(c,h)==0,"resident handles safely unloaded");
        }else if(mode=="concurrency"){''')
    (out/'test_api.cpp').write_text(test)
    ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root/usr')
    inc=[a07/'stubs',ROOT/'contracts/qwen35',ROOT/'modules/linear_A/xrt',
         ROOT/'release/a07_b04_v3/third_party/nlohmann',ROOT/'platform/qwen35/a11',source,
         ssl/'include',ssl/'include/x86_64-linux-gnu']
    command(['g++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror',
        '-DSP_LINEAR_CONTROL_TEST=1',*[f'-I{p}' for p in inc],out/'test_api.cpp',source/'backend.cpp',
        ROOT/'modules/linear_A/xrt/host_contract.cpp','-L'+str(ssl/'lib/x86_64-linux-gnu'),
        '-Wl,-rpath,'+str(ssl/'lib/x86_64-linux-gnu'),'-lcrypto','-pthread','-o',out/'control-test'],out/'compile.json',out)
    command(['/usr/bin/python3','-B',out/'run_cases.py',out/'control-test',out/'results'],out/'run.json',out)
    summary=json.loads((out/'results/summary.json').read_text())
    save(out/'SUMMARY.json',summary);print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.source,a.out)
