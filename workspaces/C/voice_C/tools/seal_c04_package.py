"""Seal the reviewed engineering package and retain the first reproduction failure."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from build_c04_candidate import manifest, archive, dump

ROOT=Path(__file__).resolve().parents[1]
ROLE=ROOT.parent
EV=ROOT/'evidence/c04'
CANDIDATE=ROLE/'releases/c04/attempt_02/C_pc_candidate_v1'


def main():
    zip_path=ROLE/'releases/c04/C_pc_candidate_v1.zip'
    if zip_path.exists():raise RuntimeError('Final zip already exists; create a new version instead')
    repro=json.loads((EV/'reproduction_02/report.json').read_text('utf-8'));assert repro['status']=='PASS'
    shutil.copyfile(EV/'reproduction_02/report.json',CANDIDATE/'evidence/independent_reproduction.json')
    shutil.copytree(EV/'reproduction_02/real_results',CANDIDATE/'evidence/independent_real_selftest')
    incident=dict(first_attempt='FAIL',failed_test='test_persistent_client_and_disabled_tts',
        reason='Optional Python network guard wrote a default stderr marker, violating the existing no-diagnostic default assertion',
        correction='Guard remains active; marker requires VOICE_C_NETWORK_GUARD_DIAGNOSTIC=1',
        old_tests_relaxed=False,first_failed_package_preserved=True,second_attempt='PASS',
        final_source_commit=repro['source_commit'])
    dump(EV/'package_reproduction_incident.json',incident)
    dump(CANDIDATE/'evidence/package_reproduction_incident.json',incident)
    (CANDIDATE/'evidence/failed_reproduction_01').mkdir()
    for name in ('unittest.log','report.json'):
        shutil.copyfile(EV/'reproduction/contract_results'/name,CANDIDATE/'evidence/failed_reproduction_01'/name)
    summary=json.loads((CANDIDATE/'ONE_PAGE_SUMMARY.json').read_text('utf-8'))
    summary['independent_reproduction']=dict(status='PASS',contract_tests=49,real_asr=True,
        real_streaming_asr=True,real_tts=True,missing_models_rejected=True,
        original_package_unchanged_after_install=True,first_failure_disclosed=True)
    dump(CANDIDATE/'ONE_PAGE_SUMMARY.json',summary)
    manifest(CANDIDATE,repro['source_commit'],reproduction=repro)
    sys.path.insert(0,str(CANDIDATE/'tools'))
    from verify_bundle import check_bundle
    static=check_bundle(CANDIDATE,CANDIDATE/'contracts/contract_lock.json')
    provenance=json.loads((CANDIDATE/'provenance/source_files.json').read_text('utf-8'))
    for row in provenance['files']:
        assert hashlib.sha256((CANDIDATE/row['path']).read_bytes()).hexdigest()==row['sha256']
    archive(CANDIDATE,zip_path)
    digest=hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sha_path=zip_path.with_suffix('.zip.sha256'); sha_path.write_text(digest+'  '+zip_path.name+'\n',encoding='ascii')
    report=dict(status='PASS_ENGINEERING_PACKAGE_SEALED',path=str(zip_path),bytes=zip_path.stat().st_size,
        sha256=digest,source_commit=repro['source_commit'],static_check=static,
        human_final_quality='NOT_TESTED',model_weights_included=False,private_audio_included=False,
        published=False,A_delivery='NOT_SENT',default_replaced=False,board='NOT_TESTED')
    dump(EV/'package_seal.json',report)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
