"""PC resource observability derivative; no changes to run/math/BO lifetime."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from derive_backend import ROOT


def main(out):
    out.mkdir(parents=True,exist_ok=False);(out/'derived').mkdir()
    prior=ROOT/'evidence/mlp_board_A/20261023-preparation-v1/pc-build-v2'
    data=(prior/'derived/backend.cpp').read_bytes()
    assert hashlib.sha256(data).hexdigest()=='56c9ff82b76dcfa4044aa63e11da7188f8a4b575b9efad7376d9ddeb39e61b06'
    text=data.decode()
    old='    if(!c->last.is_null())j.update(c->last);'
    assert text.count(old)==1
    text=text.replace(old,'''    j["a11_io_bo_addresses"]={c->x.address(),c->sx.address(),c->y.address(),c->meta.address()};
    j["a11_io_bo_charged_sizes"]={charge(8*4864,c->align),charge(8*4,c->align),charge(8*4864*4,c->align),charge(64,c->align)};
    j["a11_argument_groups"]=c->groups;
    j["a11_explicit_bo_allocations_host_counter"]=4+2*c->loads;
    j["a11_bo_counter_scope"]="host allocations for these six explicit buffers; excludes implicit XRT BOs";
    j["a11_live_weights"]=json::array();
    for(auto& item:c->weights)j["a11_live_weights"].push_back({{"handle",item.first},
        {"addresses",{item.second->w.address(),item.second->sw.address()}},
        {"charged_sizes",{charge(item.second->shape.w,c->align),charge(item.second->shape.sw,c->align)}}});
'''+old)
    (out/'derived/backend.cpp').write_text(text)
    shutil.copyfile(prior/'test_api.cpp',out/'test_api.cpp')
    shutil.copyfile(prior/'run_cases.py',out/'run_cases.py')
    commands=[]
    def call(argv):
        p=subprocess.run(argv,cwd=out,capture_output=True,text=True)
        commands.append(dict(argv=argv,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'commands.json').write_text(json.dumps(commands,indent=2))
        if p.returncode:raise RuntimeError('resource backend build/test failed')
    old_command=json.loads((prior/'command-01.json').read_text())['argv']
    argv=[arg.replace(str(prior),str(out)) for arg in old_command]
    call(argv)
    call([sys.executable,'-B',str(out/'run_cases.py'),str(out/'control-test'),str(out/'control-results')])
    call(['bash',str(ROOT/'platform/qwen35/a11/build_arm.sh'),str(out)])
    (out/'derivation.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(data).hexdigest(),
       derived_sha256=hashlib.sha256((out/'derived/backend.cpp').read_bytes()).hexdigest(),
       lib_sha256=hashlib.sha256((out/'libsp_linear_a11_trial.so').read_bytes()).hexdigest(),
       changes='report-only BO addresses/sizes/host allocation count; no new BOs or uploads',
       BOARD='NOT_TESTED'),indent=2))
    print(json.dumps(dict(PC='PASS',ARM64='CROSS_BUILD_PASS_NOT_EXECUTED',BOARD='NOT_TESTED')))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    main(ap.parse_args().out.resolve())
