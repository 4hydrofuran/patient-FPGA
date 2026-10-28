"""Build a reviewed task10 package from frozen capacity parent plus audited private timing build."""
import argparse,ast,json,shutil,tarfile
from pathlib import Path
from common import ROOT,sha,save
from step10_common import OUT

def j(p):return json.loads(p.read_text(encoding='utf-8'))

def main(variant,preflight):
    assert j(OUT/'PC_NATIVE.json')['status']=='PASS_PC_UNCHANGED_RAW_LOGITS_STATE_AND_PROFILE_CLOCKS'
    assert j(OUT/'pc-control/SUMMARY.json')['cases']==31
    assert j(OUT/'pc_supervisor_01.json')['exit_code']==0
    assert j(OUT/'pc_journal_01.json')['exit_code']==0
    if variant=='optimized':assert j(OUT/'FIX_DECISION.json')['apply_compact_completion_and_journal'] is True
    dest=OUT/variant;dest.mkdir();source=ROOT/'evidence/model_pl_A/20261024-step06-review-v1/bundle-v1'
    original=j(source/'manifest.json');assert sha(source/'manifest.json')=='469b8a99b9bcd13d4ae52eaf9add579a16ddfd94c569be6173535a4aceba97a1'
    for r in original['files']:assert sha(source/r['path'])==r['sha256']
    target=dest/'bundle-v1';shutil.copytree(source,target);(target/'manifest.json').rename(target/'capacity-parent-manifest.json')
    for p in (OUT/'arm-bin-v2').iterdir():
        if p.is_file():shutil.copyfile(p,target/'bin'/p.name)
    for p in (OUT/'source-v2').iterdir():
        if p.is_file():shutil.copyfile(p,target/'source'/p.name)
    control=target/'control';platform=target/'platform/qwen35/a12'
    frozen=j(OUT/'FROZEN_CONTROLLERS.json')['files']
    for n,pin in frozen.items():assert sha(ROOT/'platform/qwen35/a12'/n)==pin
    for n in ('step08_health.py','capacity_policy.py','window_closeout_v2.py','step07_supervisor.py','step10_window.py','step10_supervisor.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/n,platform/n)
    shutil.copyfile(ROOT/'platform/qwen35/a12/step10_manager.py',control/'step10_manager.py')
    for n in ('preflight.json','archive-pins.json'):(control/n).rename(control/('capacity-parent-'+n))
    fresh=j(preflight);assert fresh['kernel']=='6.8.12-a10irq2' and fresh['scans'][-1]['no_users_gate']
    assert not fresh['module_present'] and not fresh['active_lease_exists'] and not any(fresh['locks'].values())
    save(control/'preflight.json',fresh)
    budget=j(OUT/(variant+'-budget.json'));profile=budget['profiles'][0]
    p=target/'evidence/RESOURCE_CALL_BUDGET.json';p.rename(p.with_name('capacity-parent-resource-budget.json'));save(p,budget)
    window='a12-perf-'+variant+'-20261024-v1';remote='/var/lib/kv260-a12/step10-'+variant+'-20261024-v1'
    spec=dict(window_id=window,variant=variant,max_runs=profile['max_successful_runs'],request_limit=profile['request_limit'],
       prompt_token_limit=profile['prompt_token_limit'],output_token_limit=profile['output_token_limit'],
       max_session_seconds=profile['max_session_seconds'],receive_seconds=budget['per_request_receive_timeout_seconds'],
       compact_completion=variant=='optimized',compact_health_journal=variant=='optimized')
    save(control/'window-spec.json',spec);save(control/'requests.json',j(OUT/'REQUESTS.json')[variant])
    pins=j(source/'control/archive-pins.json');root6=ROOT/'evidence/model_pl_A/20261024-step06-review-v1'
    receipts=[root6/'readback_01/stdout.txt']
    receipts += [ROOT/f'evidence/model_pl_A/20261024-step08-v1/{v}/readback_01/stdout.txt' for v in ('diagnostic','generation')]
    receipts += [ROOT/f'evidence/model_pl_A/20261024-step09-v1/{v}/readback_01/stdout.txt' for v in ('short','context')]
    if variant=='optimized':receipts.append(OUT/'baseline/readback_01/stdout.txt')
    for receipt in receipts:
        r=j(receipt)['package']
        for k in ('path','download'):
            if k in r:pins.append(dict(path=r[k],bytes=r['bytes'],sha256=r['sha256']))
    save(control/'archive-pins.json',pins)
    save(target/'manifest.json',dict(schema_version=1,module_id='A12_STEP10_'+variant.upper()+'_V1',
       parent_manifest_sha256=sha(target/'capacity-parent-manifest.json'),contract_sha256=original['contract_sha256'],
       authorization_included=False,provider='B',maintainer='A',scope='all',budget=spec,
       files=[dict(path=p.relative_to(target).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(target.rglob('*')) if p.is_file()]))
    for p in target.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'),str(p))
    archive=dest/'bundle.tar'
    with tarfile.open(archive,'w') as tar:
        for p in sorted(target.rglob('*')):
            if p.is_file():tar.add(p,arcname=p.relative_to(target).as_posix(),recursive=False)
    up=dict(bytes=archive.stat().st_size,sha256=sha(archive),manifest_sha256=sha(target/'manifest.json'),
       remote_upload='/home/ubuntu/a12-step10-'+variant+'-20261024-v1.tar',root=remote)
    save(dest/'UPLOAD.json',up);prior=j(root6/'UPLOAD.json')
    stage=(root6/'stage_reviewed.py').read_text(encoding='utf-8').replace(repr(prior),repr(up))
    stage=stage.replace(j(root6/'preflight_01/stdout.txt')['boot_id'],fresh['boot_id'])
    (dest/'stage_reviewed.py').write_text(stage,encoding='utf-8',newline='\n')
    launch=(root6/'launch_reviewed.py').read_text(encoding='utf-8').replace(prior['root'],remote).replace(prior['manifest_sha256'],up['manifest_sha256'])
    launch=launch.replace('review06_manager.py','step10_manager.py').replace('CAPACITY_ONLY','STEP10_'+variant.upper())
    (dest/'launch_reviewed.py').write_text(launch,encoding='utf-8',newline='\n')
    read=(root6/'readback_reviewed.py').read_text(encoding='utf-8').replace(prior['root'],remote)
    read=read.replace('a12-step06-review-readback-20261024-v1.tar.gz','a12-step10-'+variant+'-readback-20261024-v1.tar.gz').replace('range(120)','range(30)')
    (dest/'readback_reviewed.py').write_text(read,encoding='utf-8',newline='\n')
    status=(root6/'status_reviewed.py').read_text(encoding='utf-8').replace(prior['root'],remote).replace('a12-capacity-20261024-v1',window)
    (dest/'status_reviewed.py').write_text(status,encoding='utf-8',newline='\n')
    monitor=(ROOT/'platform/qwen35/a12/step09_monitor_context.py').read_text(encoding='utf-8').replace('/var/lib/kv260-a12/step09-context-20261024-v1',remote)
    (dest/'monitor_reviewed.py').write_text(monitor,encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='TASK10_REVIEWED_PACKAGE_READY',variant=variant,**up)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('variant',choices=['baseline','optimized']);p.add_argument('--preflight',type=Path,required=True)
    args=p.parse_args();main(args.variant,args.preflight)
