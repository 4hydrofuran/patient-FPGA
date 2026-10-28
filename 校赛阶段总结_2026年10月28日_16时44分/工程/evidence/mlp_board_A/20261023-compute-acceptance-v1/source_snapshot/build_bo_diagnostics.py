"""Refine the observed verify_bo_ranges failure without weakening validation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[3]
PRIOR=ROOT/'evidence/mlp_board_A/20261023-integration-v1/backend-diagnostic-v2'
AUDIT=ROOT/'evidence/mlp_board_A/20261023-open-failure-review-v1/pc-audit-v1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(out):
    p=PRIOR/'derived/backend.cpp'
    assert sha(p)=='6465cb04e08b6f8014df65f864ef0e6e321a878cd4e374f84158c75118d238fe'
    text=p.read_text()
    old='    require(bo.size()==allocated&&a07::in_window(c->windows[arg][0],c->windows[arg][1],bo.address(),bo.size()),SP_DEVICE_ERROR);'
    assert text.count(old)==1
    new='''    const auto actual_size=bo.size();const auto actual_address=bo.address();
    const bool size_ok=actual_size==allocated;
    const bool range_ok=a07::in_window(c->windows[arg][0],c->windows[arg][1],actual_address,actual_size);
    const auto row=json({{"event","A11_BO_VALIDATION"},{"argument",arg},
        {"requested_bytes",allocated},{"actual_size",actual_size},{"actual_address",actual_address},
        {"window_base",c->windows[arg][0]},{"window_span",c->windows[arg][1]},
        {"size_ok",size_ok},{"range_ok",range_ok},{"compute_submissions",0}}).dump();
    std::fprintf(stderr,"%s\\n",row.c_str());std::fflush(stderr);
    require(size_ok&&range_ok,SP_DEVICE_ERROR);'''
    out.mkdir(parents=True,exist_ok=False);(out/'derived').mkdir()
    (out/'derived/backend.cpp').write_text(text.replace(old,new))
    commands=[]
    def call(argv,cwd):
        p=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=120)
        commands.append(dict(argv=argv,cwd=str(cwd),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'commands.json').write_text(json.dumps(commands,indent=2))
        assert p.returncode==0,'command failed'
        return p
    original=json.loads((AUDIT/'commands.json').read_text())
    cmd=next(r['argv'] for r in original if r['argv'][0]=='g++' and 'backend-diagnostic-v2' in ' '.join(r['argv']))
    remap={str(AUDIT/'backend-diagnostic-v2/backend.cpp'):str(out/'derived/backend.cpp'),
           str(AUDIT/'backend-diagnostic-v2/open-fault-test'):str(out/'open-fault-test')}
    assert all(k in cmd for k in remap)
    call([remap.get(x,x) for x in cmd],out)
    checked=0
    for record in original:
        argv=record['argv']
        if argv[0]!=str(AUDIT/'backend-diagnostic-v2/open-fault-test'):continue
        mode=argv[1];src=Path(record['cwd']);folder=out/mode;folder.mkdir()
        for name in ('source.json','profile.json','config.json','not-a-bitstream.txt'):
            shutil.copyfile(src/name,folder/name)
        result=call([str(out/'open-fault-test'),*argv[1:]],folder)
        assert json.loads(result.stdout)==json.loads(record['stdout'])
        rows=[json.loads(s) for s in result.stderr.splitlines() if s.startswith('{')]
        validations=[r for r in rows if r['event']=='A11_BO_VALIDATION']
        errors=[r for r in rows if r['event']=='A11_OPEN_FAILURE']
        old_errors=[json.loads(s) for s in record['stderr'].splitlines() if s.startswith('{')]
        assert errors==old_errors
        if mode=='normal':assert len(validations)==4 and all(r['size_ok'] and r['range_ok'] for r in validations)
        if mode.startswith('size_'):assert validations[-1]['size_ok'] is False
        if mode.startswith('address_'):assert validations[-1]['range_ok'] is False
        checked+=1
    assert checked==31
    call(['bash',str(ROOT/'platform/qwen35/a11/build_arm.sh'),str(out)],out)
    (out/'AUDIT.json').write_text(json.dumps(dict(status='PC_PASS_NOT_BOARD',cases=checked,
        validation_unchanged=True,math_changed=False,source_sha256=sha(out/'derived/backend.cpp'),
        library_sha256=sha(out/'libsp_linear_a11_trial.so')),indent=2))
    print((out/'AUDIT.json').read_text())

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    main(ap.parse_args().out.resolve())
