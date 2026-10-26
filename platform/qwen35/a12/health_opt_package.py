"""Additive stage from the byte-verified existing board bundle; no bulk upload."""
import base64,gzip,json,shutil,re
from pathlib import Path
from common import ROOT,sha,save

OUT=ROOT/'evidence/model_pl_A/20261024-health-opt-v1'
REMOTE='/var/lib/kv260-a12/health-opt-20261024-v1'
PARENT_REMOTE='/var/lib/kv260-a12/step10-optimized-20261024-v1'
WINDOW='a12-health-opt-20261024-v1'
def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    assert j(OUT/'pc_04.json')['exit_code']==j(OUT/'pc_integration_02.json')['exit_code']==0
    # A successful exact-source board probe is mandatory before package execution.
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--probe',required=True);args=parser.parse_args()
    assert j(OUT/args.probe/'receipt.json')['exit_code']==0
    assert j(OUT/args.probe/'stdout.txt')['status']=='PASS_READONLY_KMSG_EXACT_RAW_AND_TIMING'
    parent=ROOT/'evidence/model_pl_A/20261024-step10-v1/optimized/bundle-v1'
    target=OUT/'candidate/bundle-v1';target.parent.mkdir();shutil.copytree(parent,target)
    original=j(parent/'manifest.json');(target/'manifest.json').rename(target/'task10-parent-manifest.json')
    shutil.copyfile(OUT/'controllers/health_opt_manager.py',target/'control/health_opt_manager.py')
    shutil.copyfile(OUT/'controllers/health_opt_window.py',target/'platform/qwen35/a12/health_opt_window.py')
    shutil.copyfile(ROOT/'platform/qwen35/a12/health_opt.py',target/'platform/qwen35/a12/health_opt.py')
    fresh=j(OUT/'preflight_01/stdout.txt')
    assert fresh['kernel']=='6.8.12-a10irq2' and fresh['scans'][-1]['no_users_gate']
    assert not fresh['module_present'] and not fresh['active_lease_exists'] and not any(fresh['locks'].values())
    spec=dict(window_id=WINDOW,variant='healthopt',max_runs=5000,request_limit=3,prompt_token_limit=107,
        output_token_limit=24,max_session_seconds=1800,receive_seconds=600,compact_completion=True,compact_health_journal=True)
    def rewrite(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rewrite(target/'control/window-spec.json',spec);rewrite(target/'control/preflight.json',fresh)
    requests=j(parent/'control/requests.json');requests=[next(r for r in requests if r['id']==n) for n in ('short_profile','natural_plain','natural_profile')]
    rewrite(target/'control/requests.json',requests)
    budget=dict(schema='A12_HEALTH_OPT_BOUNDED_V1',profiles=[dict(scope='all',max_successful_runs=5000,weight_load_limit=72,
        explicit_bo_limit_bytes=140591104,request_limit=3,prompt_token_limit=107,output_token_limit=24,max_session_seconds=1800)])
    rewrite(target/'evidence/RESOURCE_CALL_BUDGET.json',budget)
    # All other asset/cache/profile checks remain as in the sealed task10 package.
    manifest=dict(schema_version=1,module_id='A12_HEALTH_OPT_V1',provider='B',maintainer='A',scope='all',
        contract_sha256=original['contract_sha256'],authorization_included=False,
        parent_manifest_sha256=sha(parent/'manifest.json'),budget=spec,
        files=[dict(path=p.relative_to(target).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(target.rglob('*')) if p.is_file()])
    save(target/'manifest.json',manifest)
    old={r['path']:r for r in original['files']}
    payload={}
    for row in manifest['files']:
        if row['path'] not in old or row['sha256']!=old[row['path']]['sha256']:
            payload[row['path']]=base64.b64encode(gzip.compress((target/row['path']).read_bytes())).decode()
    payload['manifest.json']=base64.b64encode(gzip.compress((target/'manifest.json').read_bytes())).decode()
    stage='''import base64,gzip,hashlib,json,os,shutil
from pathlib import Path
root=Path(REMOTE);parent=Path(PARENT)
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()==MACHINE
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
assert not os.path.lexists(root)
raw=(parent/'manifest.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==PARENT_PIN
old=json.loads(raw)
for r in old['files']:
 p=parent/r['path'];assert p.stat().st_size==r['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
payload=PAYLOAD
manifest_raw=gzip.decompress(base64.b64decode(payload['manifest.json']));assert hashlib.sha256(manifest_raw).hexdigest()==NEW_PIN
new=json.loads(manifest_raw)
os.umask(0o077);root.mkdir(mode=0o700)
for r in new['files']:
 name=r['path'];assert not Path(name).is_absolute() and '..' not in Path(name).parts
 data=gzip.decompress(base64.b64decode(payload[name])) if name in payload else (parent/name).read_bytes()
 assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
 dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 with dest.open('xb') as f:f.write(data)
(root/'manifest.json').write_bytes(manifest_raw);os.chmod(root/'bin/qwen35-a12',0o700)
print(json.dumps(dict(status='HEALTH_OPT_STAGED_NO_PL_MUTATION',root=str(root),files=len(new['files']))),flush=True)
'''
    tokens=dict(REMOTE=REMOTE,PARENT=PARENT_REMOTE,MACHINE=fresh['machine_sha256'],BOOT=fresh['boot_id'],PARENT_PIN=sha(parent/'manifest.json'),NEW_PIN=sha(target/'manifest.json'),PAYLOAD=payload)
    stage=re.sub(r'\b('+'|'.join(tokens)+r')\b',lambda m:repr(tokens[m[0]]),stage)
    (OUT/'stage_reviewed.py').write_text(stage,encoding='utf-8',newline='\n')
    old_remote=PARENT_REMOTE
    for name in ('launch_reviewed.py','readback_reviewed.py','status_reviewed.py','monitor_reviewed.py'):
        s=(ROOT/'evidence/model_pl_A/20261024-step10-v1/optimized'/name).read_text(encoding='utf-8')
        s=s.replace(old_remote,REMOTE).replace('a12-perf-optimized-20261024-v1',WINDOW)
        if name=='launch_reviewed.py':
            s=s.replace(sha(parent/'manifest.json'),sha(target/'manifest.json')).replace('step10_manager.py','health_opt_manager.py')
        if name=='readback_reviewed.py':s=s.replace('a12-step10-optimized-readback-20261024-v1.tar.gz','a12-health-opt-readback-20261024-v1.tar.gz')
        (OUT/name).write_text(s,encoding='utf-8',newline='\n')
    save(OUT/'PACKAGE.json',dict(status='READY_PYTHON_ONLY_CANDIDATE',manifest_sha256=sha(target/'manifest.json'),remote=REMOTE,
        binary_sha256=sha(target/'bin/qwen35-a12'),xclbin_sha256=sha(target/'w4a8.xclbin'),
        module_sha256=sha(target/'platform/qwen35/a12/health_opt.py'),requests=[r['id'] for r in requests]))
    print('HEALTH_OPT_PACKAGE_READY')
