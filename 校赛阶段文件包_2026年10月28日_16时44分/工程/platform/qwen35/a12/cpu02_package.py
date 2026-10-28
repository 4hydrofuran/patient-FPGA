"""Pinned Python-only CPU02 windows; task01 native observer and task03 unchanged."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'
PRIOR=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'
BASE=PRIOR/'integrated/bundle-v1'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def j(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,x):
    with path.open('x',encoding='utf-8') as stream:json.dump(x,stream,indent=2,ensure_ascii=False);stream.write('\n')


def main():
    assert j(OUT/'PC.json')['status'].startswith('PASS_PC')
    assert (OUT/'source/cpu02_support.py').read_bytes()==(ROOT/'platform/qwen35/a12/cpu02_support.py').read_bytes()
    for name in ('bench_baseline_02.json','bench_candidate_02.json'):
        assert j(OUT/'logs'/name)['exit_code']==0
    parent=PRIOR/'integrated/readback-v1/manifest.json';actual_parent=j(parent)
    parent_rows={r['path']:r for r in actual_parent['files']}
    old_requests=j(BASE/'control/requests.json')
    requests=[r for r in old_requests if r['id']!='short_profile']
    index=next(i for i,r in enumerate(requests) if r['id']=='natural_plain')
    requests.insert(index+1,dict(requests[index],id='natural_plain_2'))
    assert len(requests)==5
    configurations=[]
    for mode in ('baseline','candidate'):
        bundle=OUT/mode/'bundle-v1';bundle.parent.mkdir();shutil.copytree(BASE,bundle)
        if mode=='candidate':
            for p in (OUT/'source').glob('*.py'):
                dest=bundle/('control' if p.name=='cpu01_manager.py' else 'platform/qwen35/a12')/p.name
                shutil.copyfile(p,dest)
            manager=bundle/'control/cpu01_manager.py';text=manager.read_text(encoding='utf-8')
            text=text.replace('import cpu01b_observer as ob','import cpu01b_observer as ob\nfrom cpu02_support import CACHE',1)
            text=text.replace("ob.finish_request(r, case / 'management-profile.json')", "ob.finish_request(r, case / 'management-profile.json')\n        save(case / 'representation-metrics.json', dict(hits=CACHE.hits, misses=CACHE.misses, retained_snapshots=len(CACHE.entries), retained_payload_bytes=sum(len(v.payload) for v in CACHE.entries)))",1)
            compile(text,'cpu02_manager','exec');manager.write_text(text,encoding='utf-8',newline='\n')
        spec=j(BASE/'control/window-spec.json')
        spec.update(window_id='a12-cpu02-'+mode+'-20261024-v1',variant='cpu02_'+mode,request_limit=5,
            baseline_path='/var/lib/kv260-a12/cpu02-baseline-20261024-v1' if mode=='candidate' else None)
        (bundle/'control/window-spec.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
        (bundle/'control/requests.json').write_text(json.dumps(requests,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        (bundle/'cpu01-parent-manifest.json').write_bytes(parent.read_bytes())
        manifest=dict(schema_version=1,module_id='A12_CPU02_'+mode.upper(),provider='B',maintainer='A',scope='all',contract_sha256=actual_parent['contract_sha256'],
            parent_manifest_sha256=sha(parent),authorization_included=False,budget=spec)
        manifest['files']=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(bundle.rglob('*')) if p.is_file() and p!=bundle/'manifest.json']
        (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        delta={r['path']:base64.b64encode(gzip.compress((bundle/r['path']).read_bytes())).decode() for r in manifest['files'] if parent_rows.get(r['path'],{}).get('sha256')!=r['sha256']}
        configurations.append(dict(mode=mode,remote='/var/lib/kv260-a12/cpu02-'+mode+'-20261024-v1',manager='cpu01_manager.py',manifest=manifest,delta=delta))
    data=dict(parent='/var/lib/kv260-a12/cpu01-integrated-20261024-v1',parent_manifest_sha256=sha(parent),
        preflight=base64.b64encode(gzip.compress((ROOT/'platform/qwen35/a12/step06_preflight.py').read_bytes())).decode(),configurations=configurations)
    driver=(ROOT/'platform/qwen35/a12/cpu01b_board_driver.py').read_text(encoding='utf-8').replace('DATA = None','DATA = '+repr(data),1)
    driver=driver.replace("('short_profile','natural_plain','natural_profile')",repr(tuple(r['id'] for r in requests)))
    path=OUT/'board_driver_reviewed.py';path.write_text(driver,encoding='utf-8',newline='\n')
    gz=OUT/'board_driver_reviewed.py.gz';gz.write_bytes(gzip.compress(path.read_bytes()))
    remote='/home/ubuntu/a12-cpu02-driver-20261024-v1.py.gz'
    (OUT/'execute_reviewed.py').write_text("import gzip,hashlib,os\nfrom pathlib import Path\nassert os.geteuid()==0\np=Path(%r);raw=p.read_bytes()\nassert len(raw)==%d and hashlib.sha256(raw).hexdigest()==%r\nexec(compile(gzip.decompress(raw),'reviewed_cpu02_driver','exec'))\n"%(remote,gz.stat().st_size,sha(gz)),encoding='utf-8',newline='\n')
    save(OUT/'PACKAGE.json',dict(status='READY_CPU02_BASELINE_CANDIDATE_WINDOWS',driver_sha256=sha(path),gzip_sha256=sha(gz),gzip_bytes=gz.stat().st_size,
        remote_driver=remote,configurations=[dict(mode=c['mode'],remote=c['remote']) for c in configurations],calls_per_window=4896,limit=5000,
        normal_natural_repetitions=2,native_program_sha256=sha(BASE/'bin/qwen35-a12'),native_libraries_and_model_math_unchanged=True,
        fsync_per_record=True,each_submit_fresh_checks=True,default_FPGA_enabled=False,task03_changed=False,
        rollback='/var/lib/kv260-a12/cpu01-integrated-20261024-v1'))
    print('CPU02_TWO_BOUNDED_WINDOWS_PACKAGED')


if __name__=='__main__':main()
