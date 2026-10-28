"""Package one old-control and one compatible candidate with bounded diagnostics."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'
BASE=ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-bundle'
PYTHON=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1/source'


def pin(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def manager():
    text=(PYTHON/'cpu01b_manager.py').read_text(encoding='utf-8')
    text=text.replace('import cpu01b_observer as ob','import cpu01b_observer as ob\nfrom cpu01_profile import audit_profile\nfrom cpu01_numeric import compare_cases\nfrom cpu01_usage import process_usage')
    old="assert not request.get('diagnostic_dir') and (not request.get('a12_consumer_trace')) and (not request.get('state_fingerprint'))"
    new="""assert not request.get('diagnostic_dir') and not request.get('a12_consumer_trace')
        if request['id'] == 'diag_exact':
            assert request['tokens'] == list(range(1,10)) and request['teacher_tokens'] == [10,11]
            assert request['max_tokens'] == 2 and request['logits_mode'] == 'all'
            assert request['state_fingerprint'] and request['dump_state'] and request['diagnostic_all_layers']
            request['diagnostic_dir'] = str(case / 'diag')
        else:
            assert not request.get('state_fingerprint') and not request.get('dump_state')"""
    assert text.count(old)==1;text=text.replace(old,new)
    text=text.replace('ob.start_request(request)',"usage_before = process_usage(worker.process.pid)\n        ob.start_request(request)")
    text=text.replace("save(case / 'result.json', r)","save(case / 'result.json', r)\n        save(case / 'worker-usage.json', dict(before=usage_before, after=process_usage(worker.process.pid), scope='worker process CPU and main-thread context switches; reads outside client clock'))")
    text=text.replace("assert r['request_profile']['node_profile']['enabled']", "save(case / 'profile-audit.json', audit_profile(r['request_profile']))")
    anchor="ob.finish_request(r, case / 'management-profile.json')"
    addition="""
        if request['id'] == 'diag_exact':
            comparisons = {}
            if real:
                comparisons['same_candidate_S1_S2'] = compare_cases(path.parent / 's1/diag_exact', case)
            if SPEC['baseline_path']:
                comparisons['old_new_same_backend'] = compare_cases(Path(SPEC['baseline_path']) / 'run-v1' / ('s2' if real else 's1') / 'diag_exact', case)
            save(case / 'numerical-gate.json', comparisons)
        elif SPEC['baseline_path']:
            old_result = json.loads((Path(SPEC['baseline_path']) / 'run-v1' / ('s2' if real else 's1') / request['id'] / 'result.json').read_text(encoding='utf-8'))
            assert all(old_result[k] == r[k] for k in ('output_tokens','text','eos','last_prompt_logits_fnv64'))
"""
    assert text.count(anchor)==1;text=text.replace(anchor,anchor+addition.rstrip())
    compile(text,'cpu01_manager','exec')
    return text


def main():
    assert json.loads((OUT/'PC_MODEL.json').read_text(encoding='utf-8'))['status'].startswith('PASS_PC')
    assert json.loads((OUT/'logs/build_03.json').read_text(encoding='utf-8'))['exit_code']==0
    assert 'AArch64' in (OUT/'build/arm-elf.txt').read_text(encoding='utf-8')
    flags=(OUT/'build/flags.make').read_text(encoding='utf-8');assert '-mcpu=cortex-a53' in flags and '-march=native' not in flags
    source=OUT/'manager-source';source.mkdir()
    for p in PYTHON.glob('*.py'):shutil.copyfile(p,source/p.name)
    (source/'cpu01_manager.py').write_text(manager(),encoding='utf-8',newline='\n')
    for name in ('cpu01_profile.py','cpu01_numeric.py','cpu01_usage.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,source/name)
    requests=json.loads((BASE/'control/requests.json').read_text(encoding='utf-8'))
    diag=dict(requests[0],id='diag_exact',max_tokens=2,teacher_tokens=[10,11],logits_mode='all',state_fingerprint=True,dump_state=True,diagnostic_all_layers=True,profile_detail=True)
    requests=[diag,dict(requests[0],id='short_plain',profile=False),*requests]
    configurations=[]
    for mode in ('old','integrated'):
        bundle=OUT/mode/'bundle-v1';bundle.parent.mkdir();shutil.copytree(BASE,bundle)
        for p in source.glob('*.py'):
            target=bundle/('control' if p.name.endswith('manager.py') else 'platform/qwen35/a12')/p.name
            shutil.copyfile(p,target)
        if mode=='integrated':
            shutil.copyfile(OUT/'build/qwen35-a12',bundle/'bin/qwen35-a12')
            for p in (OUT/'source').iterdir():
                if p.is_file():shutil.copyfile(p,bundle/'source'/p.name)
        remote='/var/lib/kv260-a12/cpu01-'+mode+'-20261024-v1'
        spec=json.loads((BASE/'control/window-spec.json').read_text(encoding='utf-8'))
        spec.update(window_id='a12-cpu01-'+mode+'-20261024-v1',variant='cpu01_'+mode,request_limit=5,
            baseline_path='/var/lib/kv260-a12/cpu01-old-20261024-v1' if mode=='integrated' else None)
        save(bundle/'control/window-spec.json',spec);save(bundle/'control/requests.json',requests)
        (bundle/'health-parent-manifest.json').write_bytes((BASE/'manifest.json').read_bytes())
        manifest=dict(schema_version=1,module_id='A12_CPU01_'+mode.upper(),provider='B',maintainer='A',scope='all',contract_sha256=json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))['contract_sha256'],parent_manifest_sha256=pin(BASE/'manifest.json'),authorization_included=False,budget=spec)
        manifest['files']=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=pin(p)) for p in sorted(bundle.rglob('*')) if p.is_file() and p!=bundle/'manifest.json']
        save(bundle/'manifest.json',manifest)
        parent_rows={r['path']:r for r in json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))['files']}
        delta={r['path']:base64.b64encode(gzip.compress((bundle/r['path']).read_bytes())).decode() for r in manifest['files'] if parent_rows.get(r['path'],{}).get('sha256')!=r['sha256']}
        configurations.append(dict(mode=mode,remote=remote,manager='cpu01_manager.py',manifest=manifest,delta=delta))
    data=dict(parent='/var/lib/kv260-a12/health-opt-20261024-v1',parent_manifest_sha256=pin(BASE/'manifest.json'),preflight=base64.b64encode(gzip.compress((ROOT/'platform/qwen35/a12/step06_preflight.py').read_bytes())).decode(),configurations=configurations)
    driver=(ROOT/'platform/qwen35/a12/cpu01b_board_driver.py').read_text(encoding='utf-8').replace('DATA = None','DATA = '+repr(data),1)
    driver=driver.replace("('short_profile','natural_plain','natural_profile')","('diag_exact','short_plain','short_profile','natural_plain','natural_profile')")
    driver=driver.replace('Python-only','compatible CPU node and Python')
    path=OUT/'board_driver_reviewed.py';path.write_text(driver,encoding='utf-8',newline='\n')
    gz=OUT/'board_driver_reviewed.py.gz';gz.write_bytes(gzip.compress(path.read_bytes()))
    remote='/home/ubuntu/a12-cpu01-integrated-driver-20261024-v1.py.gz'
    (OUT/'execute_reviewed.py').write_text("import gzip,hashlib,os\nfrom pathlib import Path\nassert os.geteuid()==0\np=Path(%r);raw=p.read_bytes()\nassert len(raw)==%d and hashlib.sha256(raw).hexdigest()==%r\nexec(compile(gzip.decompress(raw),'reviewed_cpu01_integrated_driver','exec'))\n"%(remote,gz.stat().st_size,pin(gz)),encoding='utf-8',newline='\n')
    save(OUT/'PACKAGE.json',dict(status='READY_BOUNDED_OLD_AND_INTEGRATED_WINDOWS',driver_sha256=pin(path),gzip_sha256=pin(gz),gzip_bytes=gz.stat().st_size,remote_driver=remote,configurations=[dict(mode=c['mode'],remote=c['remote'],program_sha256=pin(OUT/c['mode']/'bundle-v1/bin/qwen35-a12')) for c in configurations],real_calls_per_window=3816,limit=5000,weights_per_window=72,numerical_gate='DIAGNOSTIC_FIRST_COMPARE_ALL_MLP_X_Y_ALL_LOGITS_AND_HYBRID_STATE_BEFORE_NORMAL_CASES',rollback='/var/lib/kv260-a12/health-opt-20261024-v1',default_backend_changed=False))
    print('CPU01_OLD_AND_INTEGRATED_PACKAGED')


if __name__=='__main__':main()
