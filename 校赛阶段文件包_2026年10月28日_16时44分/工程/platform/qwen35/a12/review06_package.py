"""New verified package for actual 72-weight residency with all compute refused."""
import ast
import json
from pathlib import Path
import shutil
import tarfile
from common import ROOT,sha,save
from review06_common import OUT

REMOTE='/var/lib/kv260-a12/step06-review-20261024-v1'

def j(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    for n in ('loadonly_pc_01','policy_pc_01','numerics_01'):
        assert j(OUT/(n+'.json'))['exit_code']==0,n
    source=ROOT/'evidence/model_pl_A/20261024-step07-mlp-v1/bundle-v1';old=j(source/'manifest.json')
    assert sha(source/'manifest.json')=='da9477f70919dcdd85829782c8117fdc1c02de0ae800106d4ab51fb327cff053'
    for r in old['files']:assert sha(source/r['path'])==r['sha256']
    target=OUT/'bundle-v1';shutil.copytree(source,target)
    (target/'manifest.json').rename(target/'mlp-parent-manifest.json')
    control=target/'control';platform=target/'platform/qwen35/a12'
    for name in ('review06_loadonly_supervisor.py','window_capacity_only.py','capacity_policy.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,platform/name)
    shutil.copyfile(ROOT/'platform/qwen35/a12/review06_manager.py',control/'review06_manager.py')
    before=control/'preflight.json';before.rename(control/'mlp-parent-preflight.json')
    pre=j(OUT/'preflight_01/stdout.txt')
    assert pre['scans'][-1]['no_users_gate'] and not pre['module_present'] and not pre['active_lease_exists'] and not any(pre['locks'].values())
    save(control/'preflight.json',pre)
    archives=[]
    for rel in ('20261023-step06-v1/readback_01/stdout.txt','20261023-step06-v1/resource_readback_01/stdout.txt',
                '20261023-step07-single-v1/stopped_readback_01/stdout.txt','20261024-step07-mlp-v1/readback_01/stdout.txt'):
        r=j(OUT.parent/rel)['package']
        for key in ('path','download'):
            if key in r:archives.append(dict(path=r[key],bytes=r['bytes'],sha256=r['sha256']))
    assert len({r['path'] for r in archives})==len(archives)
    save(control/'archive-pins.json',archives)
    assert j(OUT/'LOAD_ONLY_PC.json')['tested_source_sha256']==sha(platform/'review06_loadonly_supervisor.py')
    assert j(OUT/'WINDOW_V2_PC.json')['tested_source_sha256']==sha(platform/'window_capacity_only.py')
    for p in target.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'),str(p))
    save(target/'manifest.json',dict(schema_version=1,module_id='A12_STEP06_REVIEW_LOAD_ONLY_72_ZERO_RUNS_V1',
       execution_kind='PENDING_FRESH_LOAD_ONLY_WINDOW',authorization_included=False,scope='all',
       allowed_kernel_submissions=0,weight_load_limit=72,explicit_BO_budget_bytes=140591104,
       parent_manifest_sha256=sha(target/'mlp-parent-manifest.json'),contract_sha256=old['contract_sha256'],provider='B',maintainer='A',
       files=[dict(path=p.relative_to(target).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(target.rglob('*')) if p.is_file()]))
    archive=OUT/'capacity-only.tar'
    with tarfile.open(archive,'w') as tar:
        for p in sorted(target.rglob('*')):
            if p.is_file():tar.add(p,arcname=p.relative_to(target).as_posix(),recursive=False)
    up=dict(bytes=archive.stat().st_size,sha256=sha(archive),manifest_sha256=sha(target/'manifest.json'),
       remote_upload='/home/ubuntu/a12-step06-review-20261024-v1.tar',root=REMOTE)
    save(OUT/'UPLOAD.json',up)
    oldroot=ROOT/'evidence/model_pl_A/20261024-step07-mlp-v1';prior=j(oldroot/'UPLOAD.json')
    s=(oldroot/'stage_reviewed.py').read_text(encoding='utf-8');assert repr(prior) in s
    s=s.replace(repr(prior),repr(up)).replace('L00_MLP_NEW_BUNDLE_STAGED_NO_PL_MUTATION','CAPACITY_ONLY_NEW_BUNDLE_STAGED_NO_PL_MUTATION')
    (OUT/'stage_reviewed.py').write_text(s,encoding='utf-8',newline='\n')
    s=(oldroot/'launch_reviewed.py').read_text(encoding='utf-8')
    s=s.replace(prior['root'],REMOTE).replace(prior['manifest_sha256'],up['manifest_sha256'])
    s=s.replace('step07_mlp_manager.py','review06_manager.py').replace('L00_MLP','CAPACITY_ONLY')
    (OUT/'launch_reviewed.py').write_text(s,encoding='utf-8',newline='\n')
    s=(oldroot/'readback_reviewed.py').read_text(encoding='utf-8').replace(prior['root'],REMOTE)
    s=s.replace('a12-step07-mlp-readback-20261024-v1.tar.gz','a12-step06-review-readback-20261024-v1.tar.gz')
    s=s.replace('A12_STEP07_SINGLE_INDEPENDENT_READBACK_V1','A12_STEP06_REVIEW_INDEPENDENT_READBACK_V1')
    (OUT/'readback_reviewed.py').write_text(s,encoding='utf-8',newline='\n')
    s=(ROOT/'platform/qwen35/a12/step07_mlp_status_board.py').read_text(encoding='utf-8').replace(prior['root'],REMOTE)
    s=s.replace('a12-mlp-l00-20261024-v1','a12-capacity-20261024-v1')
    (OUT/'status_reviewed.py').write_text(s,encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='LOAD_ONLY_REVIEWED_PACKAGE_READY',archive_files=len(archives),**up)))

if __name__=='__main__':main()
