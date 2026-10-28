"""Build/test A11 derivative on PC against explicit XRT doubles, never hardware."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from derive_backend import derive, ROOT


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    derive(out/'derived')
    commands=[]

    def call(argv):
        r=subprocess.run(argv,cwd=out,capture_output=True,text=True,timeout=120)
        commands.append(dict(argv=argv,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
        with (out/f'command-{len(commands):02}.json').open('x') as f:
            json.dump(commands[-1],f,indent=2)
        if r.returncode:
            raise RuntimeError('PC build/test failed: '+r.stderr[-1000:])
        return r

    a07=ROOT/'platform/qwen35/a07/control'
    ssl=Path('/home/member-a/kv260-build/a07-pc-openssl-3.0.2-0ubuntu1.30/root/usr')
    # Re-exercise changed backend with existing 29 negative/lifecycle cases.
    # The old files/results are immutable; only the new private budget field differs.
    runner=(a07/'run_cases.py').read_text().replace("'verified_bo_budget_bytes':10000000", "'trial_bo_limit_bytes':4194304")
    runner=runner.replace("cases=['gates'", "cases=['a11_limit','gates'")
    (out/'run_cases.py').write_text(runner)
    test=(a07/'test_api.cpp').read_text()
    test=test.replace('        }else if(mode=="concurrency"){', '''        }else if(mode=="a11_limit"){
            for(unsigned j=1;j<=23;++j)check(run(j)==0,"bounded successful submission");
            auto before=control::starts;
            check(run(24)==SP_UNSUPPORTED,"24th call rejected");
            check(control::starts==before&&before==23,"limit precedes transport");
            check(control::allocations==allocs,"23 calls reuse BOs");
            check(control::count("to_5")==to_w&&control::count("to_3")==to_sw,"23 calls reuse uploads");
            auto r=report(c);check(r["output_consumable"]==false,"rejected limit invalidates old output");
            for(auto it=r.begin();it!=r.end();++it)
                if(it.key().find("a11_")==0&&it.key().find("_ms")!=std::string::npos)
                    check(it.value().is_null(),"no control-double performance");
        }else if(mode=="concurrency"){''')
    (out/'test_api.cpp').write_text(test)
    flags=['-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror']
    inc=[str(a07/'stubs'),str(ROOT/'contracts/qwen35'),str(ROOT/'modules/linear_A/xrt'),
         str(ROOT/'release/a07_b04_v3/third_party/nlohmann'),str(ROOT/'platform/qwen35/a11'),
         str(ssl/'include'),str(ssl/'include/x86_64-linux-gnu')]
    argv=['g++',*flags,'-DSP_LINEAR_CONTROL_TEST=1',*[f'-I{p}' for p in inc],
          str(out/'test_api.cpp'),str(out/'derived/backend.cpp'),str(ROOT/'modules/linear_A/xrt/host_contract.cpp'),
          '-L'+str(ssl/'lib/x86_64-linux-gnu'),'-Wl,-rpath,'+str(ssl/'lib/x86_64-linux-gnu'),
          '-lcrypto','-pthread','-o',str(out/'control-test')]
    call(argv)
    call([sys.executable,'-B',str(out/'run_cases.py'),str(out/'control-test'),str(out/'control-results')])
    call(['g++',*flags,'-I'+str(ROOT/'platform/qwen35/a11'),str(ROOT/'platform/qwen35/a11/test_lock.cpp'),'-o',str(out/'test-lock')])
    call([sys.executable,'-B',str(ROOT/'platform/qwen35/a11/test_preparation.py'),'--lock-binary',str(out/'test-lock')])
    print(json.dumps(dict(domain='PC_CONTROL_NOT_FPGA',passed=True,command_count=len(commands),BOARD='NOT_TESTED')))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    main(ap.parse_args().out.resolve())
