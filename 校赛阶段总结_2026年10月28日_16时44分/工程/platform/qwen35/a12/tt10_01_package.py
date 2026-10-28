"""One reviewed new lease, worst-case 4752/4824 submissions below the unchanged 5000 cap."""
import ast,base64,gzip,json,shutil
from pathlib import Path
from tt10_01_common import ROOT,OUT,FROZEN,j,sha,save,config


def main():
    pc=j(OUT/'PC_AUDIT_FINAL.json');assert pc['status'].startswith('PASS_FULL_PC')
    assert j(OUT/'logs/build_arm_01.json')['exit_code']==0
    flags=(OUT/'build-arm/flags.make').read_text();assert '-mcpu=cortex-a53' in flags and '-march=native' not in flags
    parent=FROZEN/'cpu02/bundle-v2';actual=FROZEN/'cpu02/readback-v1/manifest.json';parent_manifest=j(actual)
    bundle=OUT/'candidate/bundle-v1';bundle.parent.mkdir();shutil.copytree(parent,bundle)
    shutil.copyfile(OUT/'build-arm/qwen35-a12',bundle/'bin/qwen35-a12')
    for path in (OUT/'source-03').iterdir():
        if path.is_file():shutil.copyfile(path,bundle/'source'/path.name)
    for name in ('tt10_01_app.py','tt10_01_numeric.py','tt10_01_common.py','tt10_01_case.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,bundle/'platform/qwen35/a12'/name)
    original=(parent/'control/tt10_00_manager.py').read_text();module=ast.parse(original)
    node=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='run_case')
    old='\n'.join(original.splitlines()[node.lineno-1:node.end_lineno])
    entry=original.replace(old,"def run_case(worker, owner, path, *, real):\n    return execute_case(worker, owner, path, real=real, api=globals())",1)
    at=entry.index('\nSPEC =')
    entry=entry[:at]+"\nfrom tt10_01_case import execute_case\nos.environ['SP_TT10_CONFIG']=str(BUNDLE/'control/prefix-config.json')\n"+entry[at:]
    def methods(s):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(s).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name!='run_case'}
    assert methods(original)==methods(entry)
    (bundle/'control/tt10_01_manager.py').write_text(entry,encoding='utf-8',newline='\n')
    corpus=j(FROZEN/'WORKLOADS.json')['real_inputs'];full=next(r for r in corpus if r['id']=='DEV-001');n=pc['prefix_tokens']
    legacy=dict(j(parent/'control/requests.json')[0],tt10_diagnostic=True)
    diag=dict(id='diag_full_R0',op='generate',tokens=full['tokens'],teacher_tokens=[10,11],max_tokens=2,profile=True,profile_detail=True,
              prefill_chunk=256,logits_mode='all',cache_policy='R0',state_fingerprint=True,tt10_diagnostic=True)
    warm=dict(id='warm_prefix',op='cache_create',tokens=full['tokens'][:n],max_tokens=1,profile=False,cache_id='neutral',confirmed_prefix=True,
              prefill_chunk=256,logits_mode='all',cache_policy='R0',tt10_diagnostic=True)
    app={k:v for k,v in full.items() if k!='prefix_audit'};app.update(id='app_R0',max_tokens=8,profile=False,state_fingerprint=False)
    requests=[legacy,warm,diag,dict(diag,id='diag_hit',cache_policy='TT10_REQUIRE_HIT',cache_id='neutral'),app,
              dict(app,id='app_hit',cache_policy='TT10_REQUIRE_HIT',cache_id='neutral')]
    def calls(r,decode):
        count=len(r['tokens'])-(n if r['cache_policy']!='R0' else 0)
        return 72*((count+7)//8+decode)
    maximum=sum(calls(r,0 if r['op']=='cache_create' else r['max_tokens']-1) for r in requests)
    expected=sum(calls(r,0 if r['op']=='cache_create' else 6 if 'application' in r else 1) for r in requests)
    assert maximum<=5000 and (maximum,expected)==((4752,4608) if n==70 else (4824,4680))
    spec=j(bundle/'control/window-spec.json');spec.update(window_id='a12-tt10-01-20261024-v1',variant='tt10_01_full_prefix',request_limit=6,
        max_runs=5000,prompt_token_limit=128,output_token_limit=8,baseline_path=None,prefix_tokens=n,
        legacy_reference='/var/lib/kv260-a12/tt10-00-cpu02-20261024-v2')
    (bundle/'control/window-spec.json').write_text(json.dumps(spec,indent=2)+'\n')
    (bundle/'control/requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    libs={}
    for path in (bundle/'bin').glob('*.so*'):
        name=path.name.split('.so.')[0]+'.so' if '.so.' in path.name else path.name
        if name in libs:assert libs[name]==sha(path)
        libs[name]=sha(path)
    cfg=config(bundle/'bin/qwen35-a12',libs);save(bundle/'control/prefix-config.json',cfg)
    budget=j(bundle/'evidence/RESOURCE_CALL_BUDGET.json');budget['profiles'][0].update(request_limit=6,prompt_token_limit=128,output_token_limit=8)
    (bundle/'evidence/RESOURCE_CALL_BUDGET.json').write_text(json.dumps(budget,indent=2)+'\n')
    shutil.copyfile(actual,bundle/'tt10-00-parent-manifest.json')
    manifest=dict(schema_version=1,module_id='A12_TT10_01_FULL_PREFIX',provider='B',maintainer='A',scope='all',contract_sha256=parent_manifest['contract_sha256'],
                  parent_manifest_sha256=sha(actual),authorization_included=False,budget=spec)
    manifest['files']=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(bundle.rglob('*')) if p.is_file() and p!=bundle/'manifest.json']
    (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    prior={r['path']:r for r in parent_manifest['files']}
    delta={r['path']:base64.b64encode(gzip.compress((bundle/r['path']).read_bytes())).decode() for r in manifest['files'] if prior.get(r['path'],{}).get('sha256')!=r['sha256']}
    delta['control/preflight.json']=base64.b64encode(gzip.compress((bundle/'control/preflight.json').read_bytes())).decode()
    configuration=dict(mode='prefix',parent='/var/lib/kv260-a12/tt10-00-cpu02-20261024-v2',parent_manifest_sha256=sha(actual),
        remote='/var/lib/kv260-a12/tt10-01-20261024-v1',manager='tt10_01_manager.py',manifest=manifest,delta=delta)
    data=dict(preflight=base64.b64encode(gzip.compress((ROOT/'platform/qwen35/a12/step06_preflight.py').read_bytes())).decode(),configurations=[configuration])
    driver=(ROOT/'platform/qwen35/a12/cpu01b_board_driver.py').read_text().replace('DATA = None','DATA = '+repr(data),1)
    driver=driver.replace("parent=Path(DATA['parent'])","parent=Path(config['parent'])").replace("DATA['parent_manifest_sha256']","config['parent_manifest_sha256']")
    driver=driver.replace("('short_profile','natural_plain','natural_profile')",repr(tuple(r['id'] for r in requests)))
    driver=driver.replace('def preflight():','def preflight(record=None):').replace('    result=json.loads(capture.getvalue())',"    result=json.loads(capture.getvalue())\n    if record is not None:save(record,result)\n    emit('PREFLIGHT_SUMMARY',no_users=result['scans'][-1]['no_users_gate'],scan_issues=result['scans'][-1]['scan_issues'],lease=result['active_lease_exists'],module=result['module_present'],locks_free=not any(result['locks'].values()),gdm=result['gdm_state'])")
    driver=driver.replace("independent=preflight();save(root/'independent-postcheck.json',independent)","time.sleep(5)\n        independent=preflight(root/'independent-postcheck.json')")
    driver=driver.replace("delayed=preflight();save(root/'delayed-postcheck.json',delayed)","delayed=preflight(root/'delayed-postcheck.json')")
    compile(driver,'tt10_01_board_driver','exec');(OUT/'board_driver_reviewed.py').write_text(driver,encoding='utf-8',newline='\n')
    for p in bundle.rglob('*.py'):compile(p.read_text(encoding='utf-8'),str(p),'exec')
    save(OUT/'RESOURCE_CALL_BUDGET.json',dict(status='FROZEN_REVIEWED_BEFORE_BOARD',windows=1,hard_call_limit=5000,calculated_worst_case=maximum,
        expected_calls_if_same_6_token_EOS=expected,prefix_tokens=n,requests_per_backend=6,ordinary_pairs_per_backend=1,
        source_weights=72,explicit_BO_count=148,explicit_BO_bytes=140591104,max_snapshot_slots=2,slot_bytes=67108864,scratch_bytes=67108864,
        snapshot_and_scratch_total_reserve_bytes=201326592,max_session_seconds=1800,unknown_DMA_policy='RETAIN_OWNER_NO_FORCED_UNLOAD',
        ordinary_order=['R0','hit'],statistical_acceptance=False,main_goal_10s_not_relaxed=True))
    save(OUT/'PACKAGE.json',dict(status='READY_SINGLE_BOUNDED_PREFIX_WINDOW',remote=configuration['remote'],parent=configuration['parent'],
        parent_actual_manifest_sha256=sha(actual),native_sha256=sha(bundle/'bin/qwen35-a12'),manager_safety_classes_main_AST_unchanged=True,
        old_native_R0_and_default_selection_retained=True,rollback='/var/lib/kv260-a12/cpu02-candidate-20261024-v1',script_sha256=sha(OUT/'board_driver_reviewed.py')))
    print('TT10_01_BOUNDED_PACKAGE_READY')


if __name__=='__main__':main()
