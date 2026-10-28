"""Build separate on/off packages and one pinned sequential board driver."""
import base64
import gzip
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1'
PARENT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-bundle'


def pin(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for name in ('pc_03.json','equivalence_02.json'):
        if json.loads((OUT/'logs'/name).read_text(encoding='utf-8'))['exit_code']!=0:raise RuntimeError('PC prerequisite')
    configurations=[]
    for mode in ('off','on'):
        bundle=OUT/mode/'bundle-v1';bundle.parent.mkdir();shutil.copytree(PARENT,bundle)
        for path in (OUT/'source').glob('*.py'):
            target=bundle/('control' if path.name.endswith('manager.py') else 'platform/qwen35/a12')/path.name
            shutil.copyfile(path,target)
        spec=json.loads((bundle/'control/window-spec.json').read_text(encoding='utf-8'))
        spec.update(window_id='a12-cpu01b-'+mode+'-20261024-v1',variant='cpu01b_'+mode)
        (bundle/'control/window-spec.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
        (bundle/'health-parent-manifest.json').write_bytes((bundle/'manifest.json').read_bytes())
        manifest=dict(schema_version=1,module_id='A12_CPU01B_'+mode.upper(),provider='B',maintainer='A',scope='all',
            contract_sha256=json.loads((PARENT/'manifest.json').read_text())['contract_sha256'],
            parent_manifest_sha256=pin(PARENT/'manifest.json'),authorization_included=False,budget=spec,
            files=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=pin(p)) for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='manifest.json'])
        # Include nested manifests too; only the top-level manifest excludes itself.
        for p in sorted(bundle.rglob('manifest.json')):
            if p!=bundle/'manifest.json':manifest['files'].append(dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=pin(p)))
        (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        parent_rows={r['path']:r for r in json.loads((PARENT/'manifest.json').read_text())['files']}
        delta={}
        for row in manifest['files']:
            if parent_rows.get(row['path'],{}).get('sha256')!=row['sha256']:
                delta[row['path']]=base64.b64encode(gzip.compress((bundle/row['path']).read_bytes())).decode()
        configurations.append(dict(mode=mode,remote='/var/lib/kv260-a12/cpu01b-'+mode+'-20261024-v1',
            manager='cpu01b_manager.py' if mode=='on' else 'cpu01b_control_manager.py',
            manifest=manifest,delta=delta))
    data=dict(parent='/var/lib/kv260-a12/health-opt-20261024-v1',parent_manifest_sha256=pin(PARENT/'manifest.json'),
        preflight=base64.b64encode(gzip.compress((ROOT/'platform/qwen35/a12/step06_preflight.py').read_bytes())).decode(),configurations=configurations)
    driver=(ROOT/'platform/qwen35/a12/cpu01b_board_driver.py').read_text(encoding='utf-8')
    driver=driver.replace('DATA = None','DATA = '+repr(data),1)
    target=OUT/'board_driver_reviewed.py';target.write_text(driver,encoding='utf-8',newline='\n')
    (OUT/'board_driver_reviewed.py.gz').write_bytes(gzip.compress(target.read_bytes()))
    stage="import gzip,hashlib,os\nfrom pathlib import Path\nassert os.geteuid()==0\np=Path('/home/ubuntu/a12-cpu01b-driver-20261024-v1.py.gz');raw=p.read_bytes()\nassert len(raw)==%d and hashlib.sha256(raw).hexdigest()==%r\nexec(compile(gzip.decompress(raw),'reviewed_cpu01b_board_driver','exec'))\n"%((OUT/'board_driver_reviewed.py.gz').stat().st_size,pin(OUT/'board_driver_reviewed.py.gz'))
    (OUT/'execute_reviewed.py').write_text(stage,encoding='utf-8',newline='\n')
    (OUT/'PACKAGE.json').write_text(json.dumps(dict(status='READY_TWO_SEQUENTIAL_PYTHON_ONLY_WINDOWS',
        driver_sha256=pin(target),gzip_sha256=pin(OUT/'board_driver_reviewed.py.gz'),
        gzip_bytes=(OUT/'board_driver_reviewed.py.gz').stat().st_size,configurations=[dict(mode=c['mode'],remote=c['remote']) for c in configurations],
        real_calls_per_window_max=5000,weights_per_window=72,model_math_changed=False,public_ABI_changed=False,
        peer01A_03_changed=False,default_FPGA_enabled=False),indent=2)+'\n',encoding='utf-8')
    print('CPU01B_PACKAGED')


if __name__=='__main__':main()
