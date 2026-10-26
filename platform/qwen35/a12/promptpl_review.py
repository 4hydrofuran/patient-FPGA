"""Review exact private-workload derivations and artifacts; never execute ARM."""
import hashlib
from pathlib import Path
import promptpl_manager as current
import plmode_manager as parent
from promptpl_evidence import ROOT,OUT,MODE,COHORT,read,save,sha,pin

def reverse(text,edits):
    for old,new in reversed(edits):assert text.count(new)==1;text=text.replace(new,old)
    return text

def main():
    normal=read(OUT/'cohort02-AUDIT.json')['windows'];strict=read(OUT/'strict01-AUDIT.json')['windows'];faults=read(OUT/'faults01-AUDIT.json')['windows']
    assert len(normal)==25 and len(strict)==6 and len(faults)==8
    assert all(r['status']=='PASS_NORMAL_PRIVATE_CPU_WINDOW' and r['cap']==72 for r in normal)
    assert all(r['status']=='PASS_NORMAL_PRIVATE_CPU_WINDOW' and r['cap']==1 for r in strict)
    assert all(r['status']=='PASS_SPECIFIC_FAULT_WITHHELD' for r in faults)
    assert read(OUT/'WORKLOAD_POLICY_TEST.json')['count']==13
    assert read(OUT/'LIFECYCLE_FENCE_TEST.json')['status'].startswith('PASS_FRESH_LIFECYCLE_AUTHORIZATION')
    assert read(OUT/'STDOUT_BOUND_COUNTEREXAMPLE.json')['actual_stream_packets']>32
    filename=ROOT/'platform/qwen35/a12/modelpl_manager.py';pieces=[]
    for name,text,edits,original in [
        ('fixture',current.fixture_text,current.FIXTURE_EDITS,parent.method(filename,'ModelManager','_fixtures')),
        ('constructor',current.constructor,current.CTOR_EDITS,parent.constructor),
        ('init',current.init_text,current.INIT_EDITS,parent.method(ROOT/'platform/qwen35/a12/plmode_manager.py','Manager','__init__')),
        ('request',current.request,current.REQUEST_EDITS,parent.request),
        ('stdout',current.stdout_text,current.STDOUT_EDITS,parent.method(filename,'ModelManager','_stdout')),
        ('close',current.close_text,current.CLOSE_EDITS,parent.close_text),
        ('legacy',current.legacy_text,current.LEGACY_EDITS,parent.method(ROOT/'platform/qwen35/a12/plm_manager.py','Manager','_legacy_message')),
    ]:
        assert reverse(text,edits)==original
        pieces.append(dict(name=name,edits=edits,parent_sha256=hashlib.sha256(original.encode()).hexdigest()))
    original=read(MODE/'BUILD-v2.json');runtime=original['runtime_artifacts']+original['manager_artifacts']
    runtime += [dict(path=original['observer_library'],sha256=original['observer_sha256'])]
    for r in runtime:assert sha(r['path'])==r['sha256']
    quant=original['imported_quant_object'];assert sha(quant['path'])==quant['sha256']
    for row in read(OUT/'BASELINE.json')['files']:assert sha(ROOT/row['path'])==row['sha256']
    cohorts=read(OUT/'COHORTS.json')['cohorts'];assert {r['id'] for r in cohorts}=={r['cohort_id'] for r in normal}
    for row in cohorts:assert sha(row['build_path'])==row['sha256']
    for row in normal+strict+faults:
        launch=read(OUT/row['folder']/'LAUNCH.json')
        source={r['path']:r for r in launch['source']}
        for name in ('promptpl_manager.py','promptpl_workload.py'):
            p=ROOT/'platform/qwen35/a12'/name;assert sha(p)==source[p.relative_to(ROOT).as_posix()]['sha256']
    save(OUT/'FINAL_DERIVATION.json',dict(status='PASS_ALL_REVERSIBLE_EDITS',pieces=pieces,non_reversible_changes='NEW_TYPED_PC_PROVIDER_AND_PINNED_WORKLOAD_VALIDATOR_ONLY',
        existing_Board_and_native_sources_changed=False,mathematics_changed=False,ABI_changed=False))
    save(OUT/'ARTIFACT_REVIEW.json',dict(status='PASS_ACTUAL_MODEL_PRIVATE_ROUTE_FOR_FIXED_FACTS_ONLY_COHORT_PC',
        runtime_artifacts=runtime,quantization_object=quant,recompiled=False,public_ABI_unchanged=True,existing_Board_candidate_unchanged=True,
        current_normal_windows=31,current_model_answers=62,current_warm_requests=31,targeted_fault_windows=8,all_25_ids_preserved=True,
        strict_subset=['DEV-001','DEV-004','DEV-005','DEV-011','DEV-012','V08'],
        old_cohort01='DEVELOPMENT_20_NORMAL_PLUS_UNEXPECTED_V04_STARTUP_FAILURE_RETAINED_NOT_CURRENT_CODE_PROOF',
        release_allowed=False,actual_PL_results_consumed=False,BOARD='NOT_TESTED',production_enabled=False))
    print('PASS_ACTUAL_MODEL_PRIVATE_ROUTE_FIXED_COHORT_PC',31,8)
if __name__=='__main__':main()
