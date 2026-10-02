"""Run C1 structure/metric regression and C0 domain regression, with raw logs."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOG=ROOT/'bench/e2e/c1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    LOG.mkdir(parents=True,exist_ok=True)
    command_specs=[
        (['quality/c1/validate_c1.py'],'dataset_validation.log'),
        (['quality/c1/make_review_readable.py'],'review_render.log'),
        (['-m','unittest','discover','-s','quality/c1/tests','-v'],'c1_tests.log'),
        (['-m','unittest','discover','-s','app/tests','-v'],'c0_regression.log'),
        (['quality/c1/evaluate_c1.py','--output','bench/e2e/c1/readiness.json'],'readiness.log'),
        (['quality/c1/prepare_fixture.py'],'fixture_preparation.log'),
        (['quality/c1/evaluate_c1.py','--predictions','bench/e2e/c1/fixtures/predictions.synthetic.jsonl',
          '--annotations','bench/e2e/c1/fixtures/annotations.synthetic.jsonl','--output','bench/e2e/c1/fixture_evaluation.json'],'fixture_evaluation.log'),
        (['quality/c1/review_c1.py','--reviewer-1','quality/c1/review/reviewer_1_questions.template.jsonl',
          '--reviewer-2','quality/c1/review/reviewer_2_questions.template.jsonl','--output','bench/e2e/c1/review_pending.json'],'review_check.log'),
    ]
    commands=[]
    for args,name in command_specs:
        result=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60,
                              env=os.environ|{'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'})
        output=result.stdout+result.stderr
        (LOG/name).write_text(output,encoding='utf-8')
        commands.append(dict(argv=[sys.executable,*args],cwd=str(ROOT),exit_code=result.returncode,log='bench/e2e/c1/'+name))
        if result.returncode:
            (LOG/'failed_run.json').write_text(json.dumps(dict(commands=commands,failed_command=args),indent=2)+'\n',encoding='utf-8')
            print(output)
            raise SystemExit(result.returncode)
    # Keep C0 hashes historical; compare only the immutable domain/case inputs.
    old=json.loads((ROOT/'bench/e2e/c0/artifact_manifest.json').read_text(encoding='utf-8'))
    inputs=[f for f in old['files'] if f['path'].startswith(('cases/','quality/rubrics/','app/c0_domain.py','app/schemas/','app/tests/'))]
    for f in inputs:
        if sha(ROOT/f['path'])!=f['sha256']:
            raise RuntimeError('C0 domain/case input changed: '+f['path'])
    baseline=json.loads((ROOT/'quality/audit/legacy_source_hashes.json').read_text(encoding='utf-8'))
    for f in baseline['files']:
        if sha(Path(baseline['root'])/f['path'])!=f['sha256']:
            raise RuntimeError('Legacy source changed: '+f['path'])
    package_report=json.loads((ROOT/'quality/audit/package_read_report.json').read_text(encoding='utf-8'))
    for f in package_report['files']:
        if sha(ROOT.parents[1]/'KV260_三人协作执行包_20260926'/f['path'])!=f['expected']:
            raise RuntimeError('Execution package changed: '+f['path'])
    counts={name:int(re.search(r'Ran (\d+) tests', (LOG/name).read_text(encoding='utf-8')).group(1)) for name in ['c1_tests.log','c0_regression.log']}
    freeze=HERE/'frozen/freeze_manifest.json'
    frozen_manifest=json.loads(freeze.read_text(encoding='utf-8'))
    report=dict(status='PASS_PC_ENGINEERING_ONLY',timestamp_utc=datetime.now(timezone.utc).isoformat(),
        commands=commands,test_counts=counts,frozen_test_count=324,development_record_count=54,
        testset_sha256=frozen_manifest['testset_sha256'],freeze_manifest_sha256=sha(freeze),
        c0_input_files_unchanged=len(inputs),legacy_sources_unchanged=len(baseline['files']),execution_package_hashes_match=len(package_report['files']),
        medical_review='PENDING_NOT_SENT',clinical_gold='NOT_AVAILABLE',system_evaluation='NOT_RUN',teacher_mae=None,
        actual_model_and_effort='NOT_VERIFIED',model_hash=None,xclbin_hash=None,board_identity=None,git_commit=None,contract_version=None)
    (LOG/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    artifacts=[]
    for base in [HERE,LOG,ROOT/'docs/handoffs/C1.md',ROOT/'docs/status/C.md']:
        files=[base] if base.is_file() else sorted(base.rglob('*'))
        for path in files:
            if path.is_file() and '__pycache__' not in path.parts and path!=LOG/'artifact_manifest.json':
                artifacts.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
    (LOG/'artifact_manifest.json').write_text(json.dumps(dict(verification_level='PC_ENGINEERING_ONLY',files=artifacts),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'PASS: C1 {counts["c1_tests.log"]} tests; C0 {counts["c0_regression.log"]} regression tests; 324 frozen engineering questions; 54 development records.')
    print('No model/board results or teacher MAE; review remains pending.')


if __name__=='__main__':
    main()
