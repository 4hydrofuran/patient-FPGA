"""PC-only repair of missing open-failure provenance. Never deploys or retries."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]


def main(out):
    prior=ROOT/'evidence/mlp_board_A/20261023-integration-v1/backend-v1'
    data=(prior/'derived/backend.cpp').read_bytes()
    assert hashlib.sha256(data).hexdigest()=='d580ccff42b980933e5dd871048e050435c2d7413243f5c08d1a01154fceb880'
    text=data.decode();out.mkdir(exist_ok=False);(out/'derived').mkdir()
    text=text.replace('#include <cstring>','#include <cstring>\n#include <cstdio>')
    before='extern "C" int32_t sp_linear_open_v1'
    helper='''static thread_local const char* a11_open_phase="not_entered";
static void a11_open_failure(int rc) noexcept {
    try {
        std::string detail="unknown nonstandard exception";
        try {throw;} catch(const Rejected&) {detail="policy or explicit device validation rejected";}
        catch(const std::exception& e) {detail=e.what();} catch(...) {}
        if(detail.size()>512)detail.resize(512);
        const auto row=json({{"event","A11_OPEN_FAILURE"},{"phase",a11_open_phase},
            {"status_code",rc},{"detail",detail},{"compute_submissions",0},
            {"does_not_prove_resource_release",true}}).dump();
        std::fprintf(stderr,"%s\\n",row.c_str());std::fflush(stderr);
    } catch(...) {std::fputs("A11_OPEN_FAILURE_DIAGNOSTIC_UNAVAILABLE\\n",stderr);}
}
'''
    assert text.count(before)==1;text=text.replace(before,helper+before)
    a=text.index(before);b=text.index('extern "C" int32_t sp_linear_load_v1',a)
    opening=text[a:b]
    def mark(old,phase):
        nonlocal opening
        assert opening.count(old)==1,old
        opening=opening.replace(old,'a11_open_phase="'+phase+'"; '+old)
    mark('if(!out)return SP_BAD_ARGUMENT;','arguments')
    mark('auto cfg=readj(path);','config')
    mark('auto source=readj(resolve("kernel_source"));','source_gate')
    mark('auto profile=readj(resolve("deployment_profile"));','profile')
    mark('std::string bit=resolve("xclbin_path")','xclbin_hash')
    mark('auto c=std::make_unique<sp_linear_context>();','profile_layout')
    mark('c->device_lock.acquire(profile);','borrowed_lock')
    mark('c->device=xrt::device(unsigned(index));','device_open_and_name')
    mark('auto uuid=c->device.load_xclbin(bit);','load_xclbin_and_uuid')
    mark('c->kernel=xrt::kernel(','kernel_open')
    mark('auto groups=profile.at("argument_groups");','argument_groups')
    mark('c->x=xrt::bo(','allocate_x')
    mark('c->sx=xrt::bo(','allocate_sx')
    mark('c->y=xrt::bo(','allocate_y')
    mark('c->meta=xrt::bo(','allocate_meta')
    mark('check_bo(c.get(),c->x','verify_bo_ranges')
    mark('c->run=xrt::run(c->kernel);','run_object_no_submission')
    assert opening.count('}catch(...){return error();}')==1
    opening=opening.replace('}catch(...){return error();}','}catch(...){const int rc=error();a11_open_failure(rc);return rc;}')
    text=text[:a]+opening+text[b:]
    (out/'derived/backend.cpp').write_text(text)
    for name in ('test_api.cpp','run_cases.py'):shutil.copyfile(prior/name,out/name)
    commands=[]
    def call(argv):
        p=subprocess.run(argv,cwd=out,capture_output=True,text=True)
        commands.append(dict(argv=argv,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'commands.json').write_text(json.dumps(commands,indent=2))
        if p.returncode:raise RuntimeError('PC diagnostic build failed')
    old=json.loads((prior/'commands.json').read_text())[0]['argv']
    call([x.replace(str(prior),str(out)) for x in old])
    call([sys.executable,'-B',str(out/'run_cases.py'),str(out/'control-test'),str(out/'control-results')])
    expected={'device_open':'device_open_and_name','load_xclbin':'load_xclbin_and_uuid',
              'kernel_open':'kernel_open','group_id':'argument_groups','allocate':'allocate_x','bad_address':'verify_bo_ranges'}
    for case,phase in expected.items():
        rec=json.loads((out/'control-results'/('open_'+case)/'command.json').read_text())
        rows=[json.loads(x) for x in rec['stderr'].splitlines() if x.startswith('{')]
        assert len(rows)==1 and rows[0]['phase']==phase and rows[0]['compute_submissions']==0
        assert rows[0]['status_code']!=0 and rows[0]['does_not_prove_resource_release'] is True
        if case!='bad_address':assert rows[0]['detail']=='CONTROL_INJECTED_'+case
    call(['bash',str(ROOT/'platform/qwen35/a11/build_arm.sh'),str(out)])
    result=dict(status='PC_DIAGNOSTIC_REPAIR_PASS_NOT_DEPLOYED',source_sha256=hashlib.sha256(data).hexdigest(),
        derived_sha256=hashlib.sha256((out/'derived/backend.cpp').read_bytes()).hexdigest(),
        lib_sha256=hashlib.sha256((out/'libsp_linear_a11_trial.so').read_bytes()).hexdigest(),
        open_error_cases_verified=6,all_control_cases=30,public_math_changed=False,
        original_board_failure_cause='UNKNOWN_OPEN_ERROR_8_NO_EXCEPTION_DETAIL_IN_V1',
        board_retry=False,BOARD='NOT_TESTED',default_or_staged_bundle_changed=False)
    (out/'audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    main(ap.parse_args().out.resolve())
