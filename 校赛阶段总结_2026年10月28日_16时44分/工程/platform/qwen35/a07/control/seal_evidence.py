"""Final local evidence seal; reads selected files, never stages or publishes Git."""
import hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[4];E=R/'evidence/A07_closeout/20261004-v1';P=R/'release/a07_b04_v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False)
report=json.loads((E/'REPORT.json').read_text(encoding='utf-8'));status=json.loads((R/'docs/PROJECT_STATUS.json').read_text(encoding='utf-8'))
assert report['status']==status['stage_status']=='PASS_A07_OFFLINE'
assert sha(P/'files.sha256.json')==report['delivery_seal_sha256']==status['a07_closeout_seal_sha256']
assert sha(P/'artifacts/w4a8.xclbin')==status['a07_closeout_xclbin_sha256']
assert json.loads((E/'closeout-command.json').read_text())['exit_code']==0
assert json.loads((E/'package-final-verification.json').read_text())['exit_code']==0
for name in ['backend.cpp','host_contract.cpp','host_contract.hpp','release_gate.hpp','host.cpp']:
    assert sha(R/'modules/linear_A/xrt'/name)==sha(P/'modules/linear_A/xrt'/name)
lock=json.loads((R/'contracts/qwen35/contracts.lock').read_text())
assert lock['contract_sha256']==json.loads((P/'a_delivery.json').read_text())['public_contract_sha256']
for name,digest in lock['files'].items():assert sha(R/'contracts/qwen35'/name)==sha(P/'contracts/qwen35'/name)==digest
commands={}
for key,argv in [('branch',['git','branch','--show-current']),('head',['git','rev-parse','HEAD']),('status',['git','status','--porcelain=v1','--untracked-files=no'])]:
    q=subprocess.run(argv,cwd=R,capture_output=True,text=True,encoding='utf-8')
    assert q.returncode==0
    commands[key]={'argv':argv,'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
save(E/'git-final.json',commands)
paths=[R/x for x in ['docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/status/A.md','docs/handoffs/A_A07_CLOSEOUT_20261004.md']]
for folder in ['platform/qwen35/a07/control','modules/linear_A/xrt','evidence/A07_closeout/20261004-v1']:
    paths.extend(p for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='seal-evidence-v2-command.json')
save(E/'files.sha256.json',{p.relative_to(R).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(set(paths))})
save(E/'SEAL.json',{'status':'PASS_A07_OFFLINE','evidence_seal_sha256':sha(E/'files.sha256.json'),
    'delivery_seal_sha256':sha(P/'files.sha256.json'),'delivery_files':len(json.loads((P/'files.sha256.json').read_text())),
    'BOARD':'NOT_TESTED','new_commit':None,'pushed':False,'selected_production_sources_and_contract_bytes_unchanged':True})
print(json.dumps({'status':'PASS_A07_OFFLINE','delivery_files':len(json.loads((P/'files.sha256.json').read_text())),'BOARD':'NOT_TESTED'}))
