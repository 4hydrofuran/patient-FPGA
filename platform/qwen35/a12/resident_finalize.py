"""Review, preserve and seal the no-board candidate without Board activation."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import zipfile
from resident_evidence import ROOT,OUT,WORK,read,save,sha,pin
from resident_audit import audit
from plmode_runtime import machine
import resident_manager as manager
import resident_board as board
from resident_service import APP_APPEND_EDITS,app_append_text
import plm_journal
import inspect
import textwrap

NORMAL=['finalcohort'+str(i) for i in range(1,8)]+['finalflow','finalpolicy','capacity01','busy01']
FAULTS=['suite01fbeginfsync','suite01fendfsync','suite01freceiptfsync','suite01fendslow',
        'deadline02','suite01fappendfsync','deliverydeadline01','generation02','cancel01']


def reverse(text,edits):
    for old,new in reversed(edits):
        assert text.count(new)==1;text=text.replace(new,old)
    return text


def review():
    checks=read(OUT/'finalchecks01/RESULT.json');assert checks['status']=='PASS_FINAL_PC_CHECKS_AWAIT_RAW_AUDIT'
    audits=[]
    for tag in NORMAL+FAULTS:
        result=audit(tag);dest=OUT/tag/'AUDIT.json'
        if dest.exists():assert read(dest)==result
        else:save(dest,result)
        audits.append(result)
    finals=audits[:7];assert sum(q['model_answers'] for q in finals)==25
    assert audits[8]['policy_answers']==7
    cli=read(OUT/'cli01/RESULT.json');assert cli['status']=='PASS_ACTUAL_PC_CLI_TWO_ANSWERS_AND_HOST_ACK'
    assert read(OUT/'CONTROL_BOUNDARY.json')['status']=='PASS_REAL_PC_CONTROL_NINE_NOOP_REQUESTS_AND_SANITIZERS'
    for row in read(OUT/'BASELINE.json')['files']:assert sha(ROOT/row['path'])==row['sha256'],row['path']
    parent=manager.parent
    for name,edits,original in [('constructor','CTOR_EDITS','constructor'),('init_text','INIT_EDITS','init_text'),
                               ('request','REQUEST_EDITS','request'),('legacy_text','LEGACY_EDITS','legacy_text'),
                               ('close_text','CLOSE_EDITS','close_text'),('stdout_text','STDOUT_EDITS','stdout_text')]:
        assert reverse(getattr(manager,name),getattr(manager,edits))==getattr(parent,original)
    assert reverse(board.init_text,board.INIT_EDITS)==manager.init_text
    assert reverse(app_append_text,APP_APPEND_EDITS)==textwrap.dedent(inspect.getsource(plm_journal.Journal.append))
    native=read(OUT/'NATIVE_SOURCE-v1.json')
    restored=reverse((WORK/'source/main.cpp').read_text(),native['main_reversible_edits'])
    assert hashlib.sha256(restored.encode()).hexdigest()==native['original_main_sha256']
    for row in native['source']:assert sha(WORK/'source'/row['name'])==row['sha256']
    original=read(ROOT/'evidence/model_pl_A/20261026-model-route-v1/ARM_BUILD-v5.json')
    math=native['math_libraries']+original['original_math_before_and_after']+[native['imported_quant_object']]
    for row in math:assert sha(row['path'])==row['sha256']
    controls=read(OUT/'CONTROL_SOURCE-v1.json')
    for kind,key in [('pc-source','PC'),('arm-source','ARM')]:
        for row in controls[key]:assert sha(WORK/'control-v1'/kind/row['name'])==row['sha256']
    for row in read(OUT/'CONTROL_BUILD-v1.json')['artifacts']:
        assert sha(row['path'])==row['sha256']
        assert machine(row['path'])==(183 if ('a53' in row['path'] or 'resident_bound' in row['path'] or 'resident_unbound' in row['path']) else 62)
    b=read(OUT/'SERVICE_BUILD-v3.json')
    for row in b['runtime_artifacts']:assert sha(row['path'])==row['sha256']
    for field,h in [('writer_library','writer_sha256'),('observer_library','observer_sha256'),('generation_writer','generation_writer_sha256')]:
        assert sha(b[field])==b[h]
    assert sha(ROOT/'contracts/qwen35/sp_linear_v1.h')=='d97e544444b8566a32d0bd25e67e2e548f71678ac6e63ac63e96aa415b1a76f9'
    assert sha(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip')=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    times=[t for q in finals for t in q['input_to_verified_result_s']]
    status=dict(status='NOBOARD_BOUNDED_RESIDENT_CANDIDATE_REVIEWED',normal_windows=len(NORMAL),
                fixed_cohort_model_answers=25,fixed_cohort_windows=7,policy_answers=7,targeted_fault_windows=len(FAULTS),
                PC_application_s=dict(min=min(times),median=statistics.median(times),max=max(times),samples=len(times)),
                PC_pipe_complete_s=[q['host_send_to_complete_stdout_s'] for q in cli['timings']],
                startup_and_warm_s=cli['events'][0]['startup_and_warm_s'],
                tested_limits=dict(original_total_calls=5000,maximum_native_requests=9,maximum_model_requests=8,
                                   actual_short_answer_capacity_before_refusal=read(OUT/'capacity01/RESULT.json')['application_generated']),
                math_recompiled=False,public_ABI_changed=False,original_probe_changed=False,heavy_diagnostics=False,
                BOARD='NOT_TESTED',ARM_execution='NOT_EXECUTED',medical_review='PENDING_TEACHER_REVIEW',
                production_enabled=False,physical_release_allowed=False,whole_A12_goal_achieved=False,
                typed_Board_factory='PREPARED_IN_PROCESS_ONLY_FRESH_ORIGINAL_OWNER_AND_SEPARATE_TEXT_TEST_SCOPE_REQUIRED',
                remaining=['actual recovery and independent safe release','matching kernel/XRT/driver/PL',
                           'fresh Board authorization and fixed-root repinning','ordinary R0/warm/hit Board baseline first',
                           'candidate real PL numerical/content/lifecycle/resource/performance validation','medical review and production acceptance'])
    save(OUT/'TECHNICAL_REVIEW.json',dict(**status,audits=audits,mathematics_and_quantization=math,
        original_parent_files_verified=len(read(OUT/'BASELINE.json')['files']),
        settings=dict(actual_model='unknown',actual_effort='unknown'),
        delegation=dict(Sol='PC CLI transport and usage doc only; reviewed by parent',DeepSeek='mechanical parallel-task table only'),
        development_failures_retained=['pilot01','pilot02','pilot03','flow01','flow02','suite01fgeneration',
                                       'suite01fdeadline: rejected safely but initial reason matcher was insufficient',
                                       'CONTROL_BOUNDARY_RUN-ordinary.json','CONTROL_BOUNDARY_RUN-ordinary-v2.json',
                                       'initial audit grant field and original-vs-outer fence expectations corrected']))
    print(json.dumps(status,ensure_ascii=False))


def seal():
    report=read(OUT/'TECHNICAL_REVIEW.json')
    assert read(OUT/'BOARD_LAYOUT_REVIEW.json')['actual_Board_placement_verified'] is False
    assert all(q['exit_code']==0 for q in read(OUT/'FINAL_CHECK_RECEIPTS.json'))
    sources=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').glob('*resident*')) if p.is_file()]
    evidence=[pin(p) for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.zip','.pyc') and
              p.name not in ('FINAL_REVIEW.json','TERMINAL_VERIFICATION.json')]
    docs=[pin(ROOT/'docs'/p) for p in ('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md',
         'handoffs/A_A12_BOUNDED_RESIDENT_NOBOARD_20261026.md','A12_PARALLEL_PREBOARD_CLOSEOUT_20261026.md','A12_RESIDENT_PC_CLI_USAGE_20261026.md')]
    archive=OUT/'bounded-resident-review-v1.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for row in sources:z.write(ROOT/row['path'],'source/'+Path(row['path']).name)
        for name in ('TECHNICAL_REVIEW.json','SERVICE_BUILD-v3.json','resident-policy-v3.json','prefix-template-v3.json',
                     'BOARD_BUILD-v1-review-only.json','BOARD_BUILD-fixed-root-v1.json','BOARD_LAYOUT_REVIEW.json',
                     'BOARD_PREPARE-v1.json','NATIVE_REVIEW-v1.json','CONTROL_BUILD-v1.json','CONTROL_BOUNDARY.json'):
            z.write(OUT/name,'review/'+name)
        # All evidence stays on disk; include the small original application and
        # reusable staged A53 files, without copying model/weights/bitstream.
        policy=read(OUT/'resident-policy-v3.json')
        for row in policy['files']:z.write(OUT/'resident-app'/row['path'],'resident-app/'+row['path'])
        for row in read(OUT/'CONTROL_BUILD-v1.json')['artifacts']:z.write(row['path'],'compiled/'+Path(row['path']).name)
        for kind,row in read(OUT/'NATIVE_REVIEW-v1.json').items():
            if kind in ('PC','A53'):z.write(row['path'],'compiled/'+kind+'/qwen35-a12')
        for row in docs:z.write(ROOT/row['path'],'docs/'+Path(row['path']).name)
        z.writestr('README.txt','REVIEW ONLY. NOT STANDALONE OR A BOARD COMPUTE AUTHORIZATION.\n'
                   'No weights, credentials, leases or diagnostics. Requires pinned existing SDK/math/model assets.\n'
                   'CPU code is software-test only. Board default unbound backend remains unsupported.\n'
                   'Separate original Owner review, recovery, fresh release, matching kernel and ordinary baseline first.\n')
    save(OUT/'FINAL_REVIEW.json',dict(status=report['status'],source=sources,evidence=evidence,governance=docs,
         archive=pin(archive),BOARD='NOT_TESTED',production_enabled=False,physical_release_allowed=False,
         whole_A12_goal_achieved=False,independent_Board_release='NOT_PERFORMED'))
    for row in sources+evidence+docs:assert sha(ROOT/row['path'])==row['sha256']
    save(OUT/'TERMINAL_VERIFICATION.json',dict(status='ALL_SEALED_BYTES_REVERIFIED',pins=len(sources+evidence+docs),
         final_review_sha256=sha(OUT/'FINAL_REVIEW.json'),archive=pin(archive),BOARD='NOT_TESTED',release_allowed=False))
    print('SEALED_AND_REVERIFIED',len(sources+evidence+docs),sha(archive))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('review','seal'));a=p.parse_args()
    (review if a.action=='review' else seal)()
