"""Prepare a separate unconsumed window; preserve the failed v2 package/records."""
import ast,base64,difflib,gzip,json,shutil
from pathlib import Path
from tt10_01_common import ROOT,OUT,FROZEN,sha,save
def j(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    old=OUT/'window-20261025-v2';execution=old/'execution-01';post=j(execution/'independent-postcheck-01/stdout.txt')
    assert j(execution/'independent-postcheck-01/receipt.json')['exit_code']==0
    assert post['active_lease'] is None and all(not v['matching_rows'] for v in post['canonical_locks'].values())
    assert post['release_scan']['scan_complete'] and post['independent_postexit_kernel_gate']['allowed']
    assert post['failed_window_result']['status']=='FAIL_CPU_STAGE_NORMAL_FINALIZED'
    review=j(execution/'LEGACY_SCHEMA_PC_REVIEW.json');assert review['checks']==14
    parent=old/'bundle-v3';pm=j(parent/'manifest.json')
    base=OUT/'window-20261025-v3';base.mkdir(exist_ok=False);bundle=base/'bundle-v4';bundle.mkdir()
    for row in pm['files']:
        src=parent/row['path'];assert src.stat().st_size==row['bytes'] and sha(src)==row['sha256']
        dest=bundle/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    path=bundle/'platform/qwen35/a12/tt10_01_case.py';before=path.read_text(encoding='utf-8')
    first='from tt10_01_numeric import same_result,concatenated'
    added=first+'\nfrom tt10_01_legacy_compare import compare_legacy_case'
    oldblock="""            assert same_result(json.loads((old/'result.json').read_text()),r)['equal']
            a={p.name:sha(p) for p in (old/'diag').iterdir() if p.is_file()};b={p.name:sha(p) for p in (case/'diag').iterdir() if p.is_file()}
            assert a==b;save(case/'legacy-bit-exact.json',dict(status='PASS_ALL_443_FILES',files=len(a)))"""
    newblock="""            legacy=compare_legacy_case(old,case)
            save(case/'legacy-format-bridge.json',legacy)
            assert legacy['historical_comparison_pass'],legacy
            save(case/'legacy-bit-exact.json',dict(status='PASS_HISTORICAL_FIELDS_AND_ALL_ORIGINAL_RAW_BYTES',files=legacy['raw_file_count'],
                historical_final_state_sha256=legacy['historical_final_state_sha256'],terminal_sha_equality_claimed=legacy['terminal_sha_equality_claimed']))"""
    assert before.count(first)==before.count(oldblock)==1
    after=before.replace(first,added,1).replace(oldblock,newblock,1)
    assert after.replace(newblock,oldblock,1).replace(added,first,1)==before
    path.write_text(after,encoding='utf-8',newline='\n')
    shutil.copyfile(ROOT/'platform/qwen35/a12/tt10_01_legacy_compare.py',bundle/'platform/qwen35/a12/tt10_01_legacy_compare.py')
    # Numeric new/new comparison and native bytes stay identical.
    assert sha(bundle/'platform/qwen35/a12/tt10_01_numeric.py')==sha(parent/'platform/qwen35/a12/tt10_01_numeric.py')
    assert sha(bundle/'bin/qwen35-a12')==sha(parent/'bin/qwen35-a12')
    spec=j(bundle/'control/window-spec.json');spec['window_id']='a12-tt10-01-20261025-v3';write(bundle/'control/window-spec.json',spec)
    manifest={k:v for k,v in pm.items() if k!='files'}
    manifest.update(module_id='A12_TT10_01_LEGACY_SCHEMA_BRIDGE_WINDOW03',budget=spec,authorization_included=False,
        parent_prepared_manifest_sha256=sha(parent/'manifest.json'),recovery_postcheck_sha256=sha(execution/'independent-postcheck-01/stdout.txt'))
    manifest['files']=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(bundle.rglob('*')) if p.is_file()]
    write(bundle/'manifest.json',manifest)
    source=(old/'board_driver_plan.py').read_text(encoding='utf-8')
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DATA' for x in n.targets))
    data=ast.literal_eval(node.value);cfg=data['configurations'][0];cfg.update(remote='/var/lib/kv260-a12/tt10-01-20261025-v3',manifest=manifest)
    parent_rows={x['path']:x for x in j(FROZEN/'cpu02/readback-v1/manifest.json')['files']}
    cfg['delta']={x['path']:base64.b64encode(gzip.compress((bundle/x['path']).read_bytes())).decode() for x in manifest['files'] if parent_rows.get(x['path'],{}).get('sha256')!=x['sha256']}
    lines=source.splitlines(True);source=''.join(lines[:node.lineno-1])+'DATA = '+repr(data)+'\n'+''.join(lines[node.end_lineno:])
    source=source.replace('a12-tt10-01-20261025-v2','a12-tt10-01-20261025-v3')
    (base/'board_driver_plan.py').write_text(source,encoding='utf-8',newline='\n')
    for p in bundle.rglob('*.py'):compile(p.read_text(encoding='utf-8'),str(p),'exec')
    compile(source,'window03_plan','exec')
    (base/'legacy-case.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='v2/tt10_01_case.py',tofile='v3/tt10_01_case.py')),encoding='utf-8')
    changed={x['path']:x['sha256'] for x in manifest['files'] if next((r['sha256'] for r in pm['files'] if r['path']==x['path']),None)!=x['sha256']}
    assert set(changed)=={'control/window-spec.json','platform/qwen35/a12/tt10_01_case.py','platform/qwen35/a12/tt10_01_legacy_compare.py'}
    save(base/'PREPARED.json',dict(status='PC_PREPARED_UNAUTHORIZED_NEW_WINDOW_AFTER_V2_FAILURE',
        window_id='a12-tt10-01-20261025-v3',remote=cfg['remote'],local_bundle='bundle-v4',
        bundle_manifest_sha256=sha(bundle/'manifest.json'),driver_sha256=sha(base/'board_driver_plan.py'),
        native_sha256=sha(bundle/'bin/qwen35-a12'),generic_numeric_comparator_unchanged=True,
        changes=changed,legacy_final_state_SHA='NOT_AVAILABLE_NOT_INVENTED',new_R0_hit_SHA_comparison='UNCHANGED_STRICT',
        requests_unchanged=(bundle/'control/requests.json').read_bytes()==(parent/'control/requests.json').read_bytes(),
        max_runs=5000,calculated_worst_case=4752,request_count_per_backend=6,model_PC_tests_repeated=False,
        authorization_included=False,deployed=False,executed=False,BOARD='NOT_TESTED',new_PL_calls=0,TTFT_board_s=None))
    print('WINDOW03_PREPARED_NO_DEPLOYMENT_NO_COMPUTE_AUTHORIZATION')
if __name__=='__main__':main()
