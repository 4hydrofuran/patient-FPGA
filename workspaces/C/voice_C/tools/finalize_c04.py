"""Seal C04 local evidence once; never regenerate prior stage artifacts."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]; ROLE=ROOT.parent; EV=ROOT/'evidence/c04'


def write(name,data):
    (EV/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    if (EV/'artifact_manifest.json').exists():raise RuntimeError('C04 evidence is already sealed')
    baseline=json.loads((EV/'c03_mic_before_changes.json').read_text('utf-8'))
    changes=[]; same=0
    allowed={'AGENTS.md','PROJECT_STATUS.json','docs/status/C.md','voice_C/README.md','voice_C/voicec/client.py','voice_C/voicec/worker.py'}
    for row in baseline['files']:
        p=ROLE/row['path'];h=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        if h!=row['sha256']:changes.append(dict(path=row['path'],before=row['sha256'],after=h))
        else:same+=1
    assert {x['path'] for x in changes}==allowed,changes
    write('history_integrity.json',dict(baseline_files=len(baseline['files']),unchanged=same,changes=changes,
        rationale='Four live status/documents and worker/client opt-in audit argument; prior measurements/assets/configs/seals unchanged'))
    frozen=json.loads((EV/'freeze.json').read_text('utf-8'))
    for row in frozen['files']:assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256']
    tests=(EV/'unittest.log').read_text('utf-8');assert re.search(r'Ran 103 tests',tests) and tests.rstrip().endswith('OK')
    measurement=json.loads((EV/'measurements/report.json').read_text('utf-8'));assert measurement['status']=='PASS'
    assert measurement['summaries']['cold']['successes']==30 and measurement['summaries']['module']['successes']==200
    reproduction=json.loads((EV/'final_reproduction/report.json').read_text('utf-8'));assert reproduction['status']=='PASS_EXACT_FINAL_ZIP_REPRODUCTION'
    package=json.loads((EV/'package_seal.json').read_text('utf-8'));p=Path(package['path'])
    assert hashlib.sha256(p.read_bytes()).hexdigest()==package['sha256']
    arm=json.loads((EV/'arm/inspection.json').read_text('utf-8'));assert arm['status']=='PASS_STATIC_ARM_WHEEL_INSPECTION'
    verification=dict(stage='C04',status='ENGINEERING_COMPLETE_FORMAL_QUALITY_AND_LICENSE_PENDING',
        pc_checks=103,cold_workers=30,module_rounds=200,exact_zip_portable_checks=49,real_package_selftest='PASS',
        frozen_hashes='PASS',history_unchanged=same,intentional_changes=len(changes),
        physical_offline_os_reboot='NOT_TESTED',final_human_quality='NOT_TESTED',aarch64_build='NOT_TESTED',
        arm_wheel_preparation='PASS_STATIC_ONLY',board='NOT_TESTED',actual_audible_latency_ms=None,
        A_delivery='NOT_SENT',published=False,default_replaced=False,
        retained_incidents=['restricted-network ARM download failure','first package selftest stderr guard conflict',
                            'historical C02 two-probe overwrite remains disclosed'])
    write('verification.json',verification)
    command_records=[dict(action='workspace regression',command='.venv/Scripts/python.exe -m unittest discover -s tests -v',exit_code=0,log='unittest.log'),
        dict(action='ARM acquire restricted',command='tools/acquire_c04_arm.py',exit_code=1,log='arm_acquire_01.log'),
        dict(action='ARM acquire host permissions',command='tools/acquire_c04_arm.py',exit_code=0,log='arm_acquire_02.log'),
        dict(action='measurement',command='tools/measure_c04.py',exit_code=0,log='measurements.log'),
        dict(action='build first draft',command='tools/build_c04_candidate.py',exit_code=0,log='build_candidate.log'),
        dict(action='first reproduction',command='tools/reproduce_c04.py',exit_code=1,log='reproduction.log'),
        dict(action='build reviewed draft',command='tools/build_c04_candidate.py --attempt 2',exit_code=0,log='build_candidate_02.log'),
        dict(action='reviewed reproduction',command='tools/reproduce_c04.py --attempt 2',exit_code=0,log='reproduction_02.log'),
        dict(action='seal package',command='tools/seal_c04_package.py',exit_code=0,log='package_seal.log'),
        dict(action='exact final zip reproduction',command='tools/verify_final_c04.py',exit_code=0,log='final_reproduction.log')]
    write('commands.json',dict(cwd=str(ROOT),commands=command_records,source_snapshot_commands='source_snapshot_commands_02.json',
        detailed_reproduction='final_reproduction/commands.json',offline_installer='reproduction_02/commands.json'))
    paths={x['path'] for x in baseline['files']}
    for folder in ('voicec','tools','tests','bin','deploy'):
        paths.update(p.relative_to(ROLE).as_posix() for p in (ROOT/folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.md','.ps1'))
    paths.update(p.relative_to(ROLE).as_posix() for p in EV.rglob('*')
        if p.is_file() and p.name not in ('artifact_manifest.json','finalize.log'))
    paths.update(['voice_C/C04_README.md','docs/handoffs/C04.md',
                  'releases/c04/C_pc_candidate_v1.zip','releases/c04/C_pc_candidate_v1.zip.sha256'])
    rows=[]
    for name in sorted(paths):
        p=ROLE/name
        rows.append(dict(path=name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    write('artifact_manifest.json',dict(stage='C04',status=verification['status'],source_commit=None,
        candidate_source_commit=package['source_commit'],local_only=True,
        excluded=['private reproduction runtimes/model copies','.venv','.venv_mic','source snapshot .git',
                  'future manual recordings','self manifest','finalize.log'],files=rows))
    print(json.dumps(dict(status=verification['status'],sealed_files=len(rows),historical_unchanged=same,
                         intentional_changed=len(changes),candidate=package['path']),ensure_ascii=False))


if __name__=='__main__':main()
