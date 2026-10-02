"""Execute C00 checks, preserve raw logs and keep model/board domains untested."""
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CROOT=ROOT.parent
OUT=ROOT/'evidence/c00'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    commands=[]
    specs=[
        (['tools/prepare_recording_plan.py'],'recording_plan.log'),
        (['-m','unittest','discover','-s','tests','-v'],'unittest.log'),
        (['tools/collect_contract_demo.py'],'contract_demo.log'),
        (['-m','voicec.metrics','--manifest','data/recording_plan.jsonl',
          '--listening','data/tts_listening.template.jsonl','--output','evidence/c00/quality_readiness.json'],'quality_readiness.log'),
    ]
    for args,name in specs:
        result=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60,
            env=os.environ|{'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'})
        (OUT/name).write_text(result.stdout+result.stderr,encoding='utf-8')
        commands.append(dict(argv=[sys.executable,*args],cwd=str(ROOT),exit_code=result.returncode,log='voice_C/evidence/c00/'+name))
        if result.returncode:
            failure=OUT/('failed_run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
            failure.write_text(json.dumps(dict(commands=commands,status='FAIL'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(result.stdout+result.stderr)
            raise SystemExit(result.returncode)
    log=(OUT/'unittest.log').read_text(encoding='utf-8')
    count=int(re.search(r'Ran (\d+) tests',log).group(1))
    skips=int(re.search(r'skipped=(\d+)',log).group(1)) if 'skipped=' in log else 0
    sys.path.insert(0,str(ROOT))
    from voicec.dataset import validate_plan
    rows=[json.loads(s) for s in (ROOT/'data/recording_plan.jsonl').read_text(encoding='utf-8').splitlines()]
    plan=validate_plan(rows)
    # Preserve all historical C1 outputs; live C status is intentionally mutable.
    old=json.loads((CROOT/'bench/e2e/c1/artifact_manifest.json').read_text(encoding='utf-8'))
    checked=0
    for row in old['files']:
        if row['path']=='docs/status/C.md':
            continue
        if sha(CROOT/row['path'])!=row['sha256']:
            raise RuntimeError('Historical C1 artifact changed: '+row['path'])
        checked+=1
    package=CROOT/'docs/plan_qwen35'
    expected=json.loads((package/'PACKAGE_SHA256.json').read_text(encoding='utf-8'))
    for name,digest in expected.items():
        if sha(package/name)!=digest:
            raise RuntimeError('New guidance changed: '+name)
    report=dict(status='PASS_PC_CONTRACT_ONLY',verified_at_utc=datetime.now(timezone.utc).isoformat(),
        client_date='2026-10-02',client_timezone='Asia/Shanghai',stage='C00',commands=commands,
        tests_run=count,tests_passed=count-skips,tests_skipped=skips,tests_failed=0,
        execution_kind='CONTRACT_TEST',python_version=platform.python_version(),
        python_executable=sys.executable,dependency_scope='voice_C/.venv; Python standard library only; no pip packages',
        recording_plan=plan,actual_asr='NOT_TESTED',actual_tts='NOT_TESTED',
        real_cer=None,real_asr_rtf=None,real_tts_rtf=None,intelligibility=None,actual_audible_ms=None,
        aarch64_build='NOT_TESTED',board='NOT_TESTED',board_identity=None,model_hash=None,
        source_commit=None,codex_selection_actual='NOT_VERIFIED',
        historical_c1_files_unchanged=checked,package_hashes_match=len(expected),
        contract_sha256=json.loads((package/'contracts/contract_lock.json').read_text(encoding='utf-8'))['contract_sha256'])
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files=[]
    for base in [ROOT,CROOT/'PROJECT_STATUS.json',CROOT/'docs/status/C.md',CROOT/'docs/handoffs/C00.md',CROOT/'AGENTS.md']:
        for path in ([base] if base.is_file() else sorted(base.rglob('*'))):
            if (path.is_file() and not {'.venv','__pycache__','spool'} & set(path.parts)
                    and path!=OUT/'artifact_manifest.json'):
                files.append(dict(path=path.relative_to(CROOT).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
    (OUT/'artifact_manifest.json').write_text(json.dumps(dict(verification_level='PC_CONTRACT_ONLY',files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'PASS: {count-skips}/{count} C00 checks; skipped {skips}; {plan["planned"]} scripts planned, {plan["collected"]} recordings.')
    print('Persistent worker/client tested; actual speech, audio authorization, ARM64 execution and board remain untested.')


if __name__=='__main__':
    main()
