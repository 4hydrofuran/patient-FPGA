"""Prepare an independent PC package after proven recovery. No board contact."""
import ast,base64,gzip,json,shutil
from pathlib import Path
from tt10_01_common import ROOT,OUT,FROZEN,sha,save
def j(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    recovery=OUT/'recovery-authorized-20261025-v1'
    receipt=j(recovery/'independent-postcheck-01/receipt.json');assert receipt['exit_code']==0
    scene=j(recovery/'independent-postcheck-01/stdout.txt')
    assert scene['boot_id']=='1d0499ab-f1f9-438c-969a-3e701a0d806f' and scene['kernel']=='6.8.12-a10irq2'
    assert scene['active_lease'] is None and not any(v['matching_rows'] for v in scene['canonical_locks'].values())
    scan=scene['release_scan'];assert scan['scan_complete'] and not scan['scan_issues'] and not scan['device_holders'] and not scan['device_mappings']
    assert scene['gdm']['exit_code']==0 and {k:v.strip() for k,v in scene['overlays'].items()}=={'k26-starter-kits_image_1':'applied'} and not scene['module_present']
    assert scene['recovery_archive']['sha256']=='568d525f398a30b931f1767f4eec6ac19303814e781b1602d5756062f2a248e7'
    assert scene['recovery_records']['result.json']['status']=='PRIOR_BOOT_FAILED_WINDOW_ARCHIVED_RECOVERY_ONLY'
    assert scene['kernel_log']['sha256']==j(recovery/'IRQ2_KERNEL_RECOVERY_REVIEW-02.json')['raw_sha256']
    parent=OUT/'candidate/bundle-v2';pm=j(parent/'manifest.json')
    base=OUT/'window-20261025-v2';base.mkdir(exist_ok=False);bundle=base/'bundle-v3';bundle.mkdir()
    protected={}
    # Copy only original manifested files; leave historical extra bytecode untouched.
    for row in pm['files']:
        name=row['path'];assert not Path(name).is_absolute() and '..' not in Path(name).parts
        src=parent/name;assert not src.is_symlink() and src.stat().st_size==row['bytes'] and sha(src)==row['sha256']
        protected[name]=row['sha256'];dest=bundle/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    close=OUT/'cpu-close-20261025-v1/manager-source-03'
    assert sha(close/'tt10_01_manager.py')=='521090773756e7239d61b44b1c87b3bf83891a727a003ae50ec74132e7009d5a'
    assert sha(close/'tt10_01_cpu_close.py')=='6f813098e4f95d11b1c08a3d4607b9d364b7d70c5593926ec8a7490e172d1cdc'
    shutil.copyfile(close/'tt10_01_manager.py',bundle/'control/tt10_01_manager.py')
    # -I removes the script directory: use the manager's explicit import path.
    shutil.copyfile(close/'tt10_01_cpu_close.py',bundle/'platform/qwen35/a12/tt10_01_cpu_close.py')
    for name in ('tt10_01_case.py','tt10_01_numeric.py','tt10_01_app.py','tt10_01_common.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,bundle/'platform/qwen35/a12'/name)
    binary=OUT/'build-arm04/qwen35-a12';assert sha(binary)=='115d167265667f026594836760be12470876e2b001b9dc8b61773459da35efab'
    shutil.copyfile(binary,bundle/'bin/qwen35-a12')
    for p in (OUT/'source-04').iterdir():
        if p.is_file():shutil.copyfile(p,bundle/'source'/p.name)
    cfg=j(bundle/'control/prefix-config.json');cfg['identity']['executable_sha256']=sha(binary);write(bundle/'control/prefix-config.json',cfg)
    window='a12-tt10-01-20261025-v2';remote='/var/lib/kv260-a12/tt10-01-20261025-v2'
    spec=j(bundle/'control/window-spec.json');spec['window_id']=window;write(bundle/'control/window-spec.json',spec)
    assert spec['max_runs']==5000 and spec['request_limit']==6 and spec['prefix_tokens']==70
    assert (bundle/'control/requests.json').read_bytes()==(parent/'control/requests.json').read_bytes()
    budget=j(OUT/'RESOURCE_CALL_BUDGET.json');assert budget['calculated_worst_case']==4752
    budget.update(status='PREPARED_NOT_AUTHORIZED_EXECUTION',window_id=window);write(base/'RESOURCE_CALL_BUDGET.json',budget)
    # The driver must refresh this placeholder under the future exact preflight.
    write(bundle/'control/preflight.json',dict(placeholder=True,compute_review='PENDING',expected_boot=scene['boot_id'],source='independent-postcheck-01'))
    manifest={k:v for k,v in pm.items() if k!='files'}
    manifest.update(module_id='A12_TT10_01_SOURCE04_CPU_CLOSE_WINDOW02',budget=spec,authorization_included=False,
        preparation_status='PC_PREPARED_NOT_DEPLOYED',recovery_postcheck_sha256=sha(recovery/'independent-postcheck-01/stdout.txt'))
    manifest['files']=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(bundle.rglob('*')) if p.is_file()]
    write(bundle/'manifest.json',manifest)
    source=(OUT/'board_driver_reviewed02.py').read_text(encoding='utf-8')
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DATA' for x in n.targets))
    data=ast.literal_eval(node.value);c=data['configurations'][0];c.update(remote=remote,manifest=manifest)
    parent_rows={r['path']:r for r in j(FROZEN/'cpu02/readback-v1/manifest.json')['files']}
    c['delta']={r['path']:base64.b64encode(gzip.compress((bundle/r['path']).read_bytes())).decode() for r in manifest['files'] if parent_rows.get(r['path'],{}).get('sha256')!=r['sha256']}
    lines=source.splitlines(True);source=''.join(lines[:node.lineno-1])+'DATA = '+repr(data)+'\n'+''.join(lines[node.end_lineno:])
    marker="fresh=preflight();emit('FRESH_GATE_PASS'"
    assert source.count(marker)==1
    source=source.replace(marker,"fresh=preflight();assert fresh['boot_id']=='"+scene['boot_id']+"';emit('FRESH_GATE_PASS'",1)
    entry="if __name__=='__main__':raise SystemExit(main())"
    assert source.count(entry)==1
    source=source.replace(entry,"""if __name__=='__main__':
    if sys.argv[1:]!=['--execute-reviewed-window','a12-tt10-01-20261025-v2']:
        print(json.dumps(dict(status='PLAN_ONLY_NOT_AUTHORIZED',window='a12-tt10-01-20261025-v2',board_contact=False)))
        raise SystemExit(0)
    raise SystemExit(main())""")
    driver=base/'board_driver_plan.py';driver.write_text(source,encoding='utf-8',newline='\n')
    for p in bundle.rglob('*.py'):compile(p.read_text(encoding='utf-8'),str(p),'exec')
    compile(source,str(driver),'exec')
    assert all(sha(parent/name)==pin for name,pin in protected.items())
    status=dict(status='PC_PACKAGE_PREPARED_REQUIRES_SCOPED_COMPUTE_REVIEW',window_id=window,remote=remote,
        bundle_manifest_sha256=sha(bundle/'manifest.json'),driver_sha256=sha(driver),native_sha256=sha(binary),
        manager_sha256=sha(bundle/'control/tt10_01_manager.py'),cpu_close_sha256=sha(bundle/'platform/qwen35/a12/tt10_01_cpu_close.py'),
        original_manifest_files_unchanged=len(protected),copied_extra_bytecode=False,requests_unchanged=True,
        original_thresholds_and_math_unchanged=True,driver_default='PLAN_ONLY',source03_model_rerun=False,
        deployed=False,compute_authorization_included=False,BOARD='NOT_TESTED',new_PL_calls=0,TTFT_board_s=None,
        remaining=['Fresh compute-specific baseline/resource/namespace/dual-lock review','Explicit scoped compute authorization before staging/execution','Actual CPU close and R0/hit numerical/timing verification on board'])
    save(base/'PREPARED.json',status);print(json.dumps(status),flush=True)
if __name__=='__main__':main()
