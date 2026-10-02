"""Re-extract the exact final ZIP and independently install/run its selftest."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from reproduce_c04 import extract_checked

ROOT=Path(__file__).resolve().parents[1]; ROLE=ROOT.parent


def main():
    evidence=ROOT/'evidence/c04/final_reproduction';evidence.mkdir(exist_ok=False)
    base=ROLE/'releases/c04';archive=base/'C_pc_candidate_v1.zip'
    expected=json.loads((ROOT/'evidence/c04/package_seal.json').read_text('utf-8'))
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected['sha256']
    source=base/'final_independent_source';runtime=base/'final_independent_runtime'
    extract_checked(archive,source)
    sys.path.insert(0,str(source/'tools'))
    from verify_bundle import check_bundle
    before=check_bundle(source,source/'contracts/contract_lock.json')
    manifest=json.loads((source/'manifest.json').read_text('utf-8'))
    assert not any(x['path'].endswith(('.onnx','.pcm')) for x in manifest['files'])
    assert [x['path'] for x in manifest['files'] if x['path'].endswith('.wav')]==['data/c04_public_smoke.wav']
    env=os.environ|dict(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(source/'tools/c04_network_guard'),VOICE_C_NETWORK_GUARD_DIAGNOSTIC='0')
    commands=[
        [sys.executable,str(source/'tools/install_candidate.py'),'--target-runtime',str(runtime)],
        [sys.executable,str(source/'tools/materialize_local_assets.py'),'--source-voice-root',str(ROOT),'--target-runtime',str(runtime)],
        [str(runtime/'.venv/Scripts/python.exe'),str(runtime/'bin/selftest.py'),'--real','--output',str(evidence/'selftest')]]
    records=[]
    for i,cmd in enumerate(commands):
        proc=subprocess.run(cmd,cwd=source,capture_output=True,text=True,encoding='utf-8',timeout=180,env=env)
        (evidence/f'command_{i:02}.log').write_text(proc.stdout+proc.stderr,encoding='utf-8')
        records.append(dict(argv=cmd,exit_code=proc.returncode))
        (evidence/'commands.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        assert proc.returncode==0, f'Final reproduction command {i} failed'
    tested=json.loads((evidence/'selftest/report.json').read_text('utf-8'))
    assert tested['status']=='PASS' and tested['real_status']=='PASS' and tested['contract_tests']==49
    after=check_bundle(source,source/'contracts/contract_lock.json')
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected['sha256']
    report=dict(status='PASS_EXACT_FINAL_ZIP_REPRODUCTION',zip_sha256=expected['sha256'],
        static_before=before,static_after=after,contract_tests=49,real_asr=True,real_streaming_asr=True,real_tts=True,
        package_unchanged=True,private_model_materialization='SAME_MACHINE_NOT_IN_ZIP',
        source_commit=manifest['source_commit'],microphone_opened=False,board='NOT_TESTED')
    (evidence/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
