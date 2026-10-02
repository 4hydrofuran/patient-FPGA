"""Validate a separately extracted package, offline install and real local smoke."""
import hashlib
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ROLE=ROOT.parent
EV=ROOT/'evidence/c04/reproduction'
BASE=ROLE/'releases/c04'


def extract_checked(archive,target):
    target.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP entries')
        if sum(x.file_size for x in z.infolist())>512*1024*1024:raise ValueError('ZIP size exceeds declared bound')
        for info in z.infolist():
            name=info.filename
            if '\\' in name or ':' in name or PurePosixPath(name).is_absolute() or any(x in ('','..','.') for x in name.split('/')):
                raise ValueError('Unsafe ZIP path')
            if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('ZIP contains symlink')
            p=target/name
            if not p.resolve().is_relative_to(target.resolve()):raise ValueError('ZIP path escapes target')
            p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f:f.write(z.read(info))


def main():
    global EV,BASE
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',type=int,default=1,choices=range(1,10))
    args=parser.parse_args()
    if args.attempt!=1:
        EV=ROOT/f'evidence/c04/reproduction_{args.attempt:02}'
        BASE=ROLE/f'releases/c04/attempt_{args.attempt:02}'
    EV.mkdir(exist_ok=False)
    source=BASE/'independent_source';runtime=BASE/'independent_runtime'
    archive_name='preflight_package.zip' if args.attempt==1 else f'preflight_package_{args.attempt:02}.zip'
    extract_checked(ROOT/'evidence/c04'/archive_name,source)
    records=[]
    env=os.environ|dict(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(source/'tools/c04_network_guard'),VOICE_C_NETWORK_GUARD_DIAGNOSTIC='0')
    def run(name,argv,expected=0):
        proc=subprocess.run([str(x) for x in argv],cwd=source,capture_output=True,text=True,
            encoding='utf-8',timeout=180,env=env)
        (EV/(name+'.log')).write_text(proc.stdout+proc.stderr,encoding='utf-8')
        records.append(dict(name=name,argv=[str(x) for x in argv],exit_code=proc.returncode,expected_exit=expected))
        (EV/'commands.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        if proc.returncode!=expected:raise RuntimeError(name+' failed; see preserved log')
        print(name,'EXPECTED_EXIT',expected,flush=True)
    run('static',[sys.executable,source/'tools/verify_bundle.py',source,'--contract',source/'contracts/contract_lock.json'])
    run('network_guard_probe',[sys.executable,'-c',"import sys,socket; assert sys._voicec_network_guard; s=socket.socket(); s.connect(('1.1.1.1',443))"],expected=1)
    assert 'C04 test forbids Python network access' in (EV/'network_guard_probe.log').read_text('utf-8')
    run('installation',[sys.executable,source/'tools/install_candidate.py','--target-runtime',runtime])
    python=runtime/'.venv/Scripts/python.exe'
    run('contract',[python,runtime/'bin/selftest.py','--output',EV/'contract_results'])
    run('missing_models',[python,runtime/'bin/selftest.py','--real','--output',EV/'missing_models_results'],expected=1)
    missing=json.loads((EV/'missing_models_results/report.json').read_text('utf-8'))
    assert missing['status']=='FAIL' and missing['real_status']=='FAIL'
    run('local_asset_materialization',[sys.executable,source/'tools/materialize_local_assets.py',
        '--source-voice-root',ROOT,'--target-runtime',runtime])
    run('real',[python,runtime/'bin/selftest.py','--real','--output',EV/'real_results'])
    run('static_after_install',[sys.executable,source/'tools/verify_bundle.py',source,'--contract',source/'contracts/contract_lock.json'])
    real=json.loads((EV/'real_results/report.json').read_text('utf-8'))
    assert real['status']=='PASS' and real['real_status']=='PASS' and real['worker_exit_code']==0
    expected=json.loads((source/'manifest.json').read_text('utf-8'))
    actual=subprocess.check_output(['git','bundle','list-heads',str(source/'provenance/source_snapshot.bundle')],text=True)
    assert expected['source_commit'] in actual
    for row in json.loads((source/'provenance/source_files.json').read_text('utf-8'))['files']:
        assert hashlib.sha256((source/row['path']).read_bytes()).hexdigest()==row['sha256']
    report=dict(status='PASS',fresh_extraction=True,static_before_and_after='PASS',
        source_commit=expected['source_commit'],git_bundle_head_verified=True,
        contract_tests=real['contract_tests'],real_asr=True,real_streaming_asr=True,real_tts=True,
        missing_models_rejected=True,offline_installer=True,model_assets_in_zip=False,
        local_model_copy='SAME_MACHINE_PRIVATE_RUNTIME_ONLY',global_environment_modified=False,
        source_directory=str(source),runtime_directory=str(runtime),microphone_opened=False,
        physical_offline_reboot='NOT_TESTED',human_final_quality='NOT_TESTED',board='NOT_TESTED',commands=records)
    (EV/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
