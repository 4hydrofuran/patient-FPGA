"""Create additive reviewed single-projection deployment, stage/launch/readback scripts."""
import json
from pathlib import Path
import shutil
import tarfile
from common import ROOT,sha,save
from step07_protocol import OUT

REMOTE='/var/lib/kv260-a12/step07-single-20261023-v1'


def main():
    source=ROOT/'release/a12_preboard_20261023_v1'
    original=json.loads((source/'manifest.json').read_text())
    for row in original['files']:
        p=source/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    target=OUT/'bundle-v1';shutil.copytree(source,target)
    (target/'manifest.json').rename(target/'base-manifest.json')
    build=json.loads((OUT/'BUILD.json').read_text())
    for name,row in build['files'].items():
        p=Path(row['path']);assert sha(p)==row['sha256'];shutil.copyfile(p,target/'bin'/name)
    for p in (OUT/'source-v1').iterdir():
        if p.is_file():shutil.copyfile(p,target/'source'/p.name)
    platform=target/'platform/qwen35/a12'
    for name in ('step07_supervisor.py',):shutil.copyfile(ROOT/'platform/qwen35/a12'/name,platform/name)
    p=platform/'window.py';s=p.read_text();assert s.count('from supervisor import OwnedWorker')==1
    s=s.replace('from supervisor import OwnedWorker','from step07_supervisor import OwnedWorker')
    s=s.replace('baseline.read_text()','baseline.read_bytes().decode(\'utf-8\')')
    p.write_text(s,encoding='utf-8',newline='\n')
    control=target/'control';control.mkdir();support=control/'support';support.mkdir()
    old=ROOT/'evidence/mlp_board_A/20261023-compute-acceptance-v1/bundle-v2'
    old_manifest=json.loads((old/'manifest.json').read_text())
    for name in ('mlp_base.py','mlp_kernel_gate.py','xrt_worker_boundary.py','idle_board_trial.py',
                 'accelerator_release_gate_v2.py','isolated_idle_policy.py','kernel_log_gate.py'):
        assert sha(old/name)==old_manifest['files'][name]['sha256'];shutil.copyfile(old/name,support/name)
    hardware=target/'hardware';hardware.mkdir()
    for name in ('a11-mlp.bit.bin','a11-mlp.dtbo','shell.json','zocl.refcount.ko'):
        assert sha(old/name)==old_manifest['files'][name]['sha256'];shutil.copyfile(old/name,hardware/name)
    shutil.copyfile(ROOT/'platform/qwen35/a12/step07_manager.py',control/'step07_manager.py')
    preflight=json.loads((OUT/'preflight_01/stdout.txt').read_text())
    assert preflight['kernel']=='6.8.12-a10irq2' and preflight['scans'][-1]['no_users_gate']
    assert not preflight['active_lease_exists'] and not preflight['module_present'] and not any(preflight['locks'].values())
    save(control/'preflight.json',preflight)
    assets=json.loads((OUT.parent/'20261023-step06-v1/deployment-manifest.json').read_text())
    save(control/'asset-pins.json',{n[len('assets/'):]:v['sha256'] for n,v in assets['files'].items() if n.startswith('assets/')})
    request=json.loads((OUT.parent/'20261023-step06-v1/requests.json').read_text())[0];request.pop('diagnostic')
    save(control/'request.json',request)
    save(target/'manifest.json',dict(schema_version=1,module_type='linear',module_id='A12_STEP07_SINGLE_GATE_CANDIDATE_V1',
        authorization_included=False,execution_kind='PENDING_FRESH_SINGLE_PROJECTION_WINDOW',
        base_manifest_sha256=sha(target/'base-manifest.json'),scope='l0_gate',max_loads=1,max_runs=17,
        explicit_BO_budget_bytes=2162688,contract_sha256=original['contract_sha256'],provider='B',maintainer='A',
        files=[dict(path=p.relative_to(target).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
               for p in sorted(target.rglob('*')) if p.is_file()]))
    archive=OUT/'single-gate.tar'
    with tarfile.open(archive,'w') as tar:
        for p in sorted(target.rglob('*')):
            if p.is_file():tar.add(p,arcname=p.relative_to(target).as_posix(),recursive=False)
    upload=dict(bytes=archive.stat().st_size,sha256=sha(archive),manifest_sha256=sha(target/'manifest.json'),
                remote_upload='/home/ubuntu/a12-step07-single-20261023-v1.tar',root=REMOTE)
    save(OUT/'UPLOAD.json',upload)
    stage='''import hashlib,json,os,shutil,subprocess,tarfile
from pathlib import Path
up=UPLOAD
root=Path(up['root']);archive=Path(up['remote_upload'])
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()==MACHINE
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
assert not os.path.lexists(root)
assert archive.stat().st_size==up['bytes'] and hashlib.sha256(archive.read_bytes()).hexdigest()==up['sha256']
os.umask(0o077)
with tarfile.open(archive) as tar:
 members=tar.getmembers();assert len(members)==len({m.name for m in members})
 assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
 raw=tar.extractfile('manifest.json').read();assert hashlib.sha256(raw).hexdigest()==up['manifest_sha256']
 manifest=json.loads(raw);assert {m.name for m in members}=={r['path'] for r in manifest['files']}|{'manifest.json'}
 for r in manifest['files']:
  data=tar.extractfile(r['path']).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
 root.mkdir(mode=0o700)
 for m in members:
  dest=root/m.name;dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with dest.open('xb') as f:shutil.copyfileobj(tar.extractfile(m),f)
 os.chmod(root/'bin/qwen35-a12',0o700)
 env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_'))};env['LD_LIBRARY_PATH']=str(root/'bin')
 r=subprocess.run(['ldd',str(root/'bin/qwen35-a12')],env=env,capture_output=True,text=True,timeout=10)
 assert r.returncode==0 and 'not found' not in r.stdout and 'libxrt_' not in r.stdout
 (root/'ldd.txt').write_text(r.stdout)
print(json.dumps(dict(status='SINGLE_GATE_NEW_BUNDLE_STAGED_NO_PL_MUTATION',root=str(root),files=len(manifest['files']))),flush=True)
'''
    stage=stage.replace('up=UPLOAD','up='+repr(upload)).replace('==MACHINE','=='+repr(preflight['machine_sha256'])).replace('==BOOT','=='+repr(preflight['boot_id']))
    (OUT/'stage_reviewed.py').write_text(stage)
    wrapper='''import json,subprocess,os
from pathlib import Path
root=Path(ROOT)
with (root/'manager.stdout.jsonl').open('x') as out,(root/'manager.stderr.txt').open('x') as err:
 p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(root/'control/step07_manager.py')],stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True)
 with (root/'manager-pid.json').open('x') as f:json.dump(dict(pid=p.pid,wrapper_pid=os.getpid()),f)
 rc=p.wait()
 with (root/'manager-exit.json').open('x') as f:json.dump(dict(pid=p.pid,exit_code=rc),f)
'''.replace('Path(ROOT)','Path('+repr(REMOTE)+')')
    launch='''import hashlib,json,os,subprocess
from pathlib import Path
root=Path(ROOT)
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()==PIN
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
assert not (root/'run-v1').exists()
(root/'SINGLE_GATE_LAUNCH_RESERVED').touch(exist_ok=False)
wrapper=WRAPPER
p=subprocess.Popen(['/usr/bin/python3','-B','-I','-c',wrapper],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
print(json.dumps(dict(status='SINGLE_GATE_MANAGER_DISPATCHED_ONCE',wrapper_pid=p.pid)),flush=True)
'''.replace('Path(ROOT)','Path('+repr(REMOTE)+')').replace('==PIN','=='+repr(upload['manifest_sha256'])).replace('wrapper=WRAPPER','wrapper='+repr(wrapper))
    (OUT/'launch_reviewed.py').write_text(launch)
    read=(ROOT/'platform/qwen35/a12/step06_readback.py').read_text()
    read=read.replace('/var/lib/kv260-a12/step06-20261023-v1',REMOTE)
    read=read.replace("str(ROOT/'control')","str(ROOT/'control/support')")
    read=read.replace("ROOT/'run-v1/STOP.json'","ROOT/'run-v1/s2/ISOLATED.json'")
    read=read.replace("'run-v1/STOP.json','run-v1/result.json','run-v1/worker-identity.json','run-v1/ready.json'",
                      "'run-v1/s2/ISOLATED.json','run-v1/result.json','run-v1/s2/identity.json','run-v1/s2/result.json'")
    read=read.replace("'deployment-manifest.json'","'manifest.json'")
    read=read.replace('A12_STEP06_INDEPENDENT_READBACK_V1','A12_STEP07_SINGLE_INDEPENDENT_READBACK_V1')
    read=read.replace('a12-step06-readback-20261023-v1.tar.gz','a12-step07-single-readback-20261023-v1.tar.gz')
    (OUT/'readback_reviewed.py').write_text(read)
    print(json.dumps(dict(status='SINGLE_GATE_PACKAGE_AND_REVIEWED_SCRIPTS_READY',**upload)))


if __name__=='__main__':main()
