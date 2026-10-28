"""Audit final native A/B artifacts and real fault runs; keep whole goal active."""
import json
from pathlib import Path
import shutil
from native_cpu_build import ROOT,OUT,read,save,sha
from native_request_journal import DOMAIN,digest
from native_request_audit import audit
from resource_probe_policy import ordinary_comparison
from request_journal_verified import require


def main():
    build=read(OUT/'BUILD-v2.json')
    require(sha(ROOT/'platform/qwen35/a12/native_cpu_control.cpp')==build['source_sha256'],'current C++ source differs from built adapter')
    require(read(OUT/'abi-tests-02/RESULT.json')['status']=='PASS' and
        read(OUT/'integration-tests-02/RESULT.json')['status']=='PASS','targeted tests missing/failing')
    require(read(OUT/'abi-tests-01/RESULT.json')['status']=='FAIL','old ABI failure lost')
    require((OUT/'integration-tests-01/HARNESS_FAILURE.json').is_file(),'old harness failure lost')
    require(read(OUT/'ARTIFACT_AUDIT.json')['status'].startswith('PASS_'),'ELF/ABI audit missing')
    reports={};audits={};timings=[];copied=[]
    target=OUT/'native-transcripts';target.mkdir(exist_ok=False)
    for mode in ('strict','request'):
        directory=OUT/('run-'+mode+'-v2-02');report=read(directory/'RESULT.json');reports[mode]=report
        require(report['status']=='PASS_ACTUAL_PC_MODEL_WITH_REQUEST_JOURNAL' and report['worker_exit_code']==0
            and report['worker_closed'] is True and report['fault_injection'] is None and report['raw_diagnostic_files']==0,
            'final native run incomplete')
        for row in read(directory/'SOURCE_AT_LAUNCH.json'):
            require(sha(ROOT/row['path'])==row['sha256'],'final A/B did not use current Python source')
        worker=Path(report['workspace'])/'worker';result=audit(worker,OUT/'BUILD-v2.json');audits[mode]=result
        require(result['status']=='COMPLETE_ACTUAL_PC_NATIVE_TRANSCRIPT' and result['actual_cpu_calls']==2880,
                'independent native audit failed')
        save(directory/'INDEPENDENT_AUDIT.json',result)
        for name in ('app_R0','app_hit'):
            clock=read(directory/name/'application-timing.json');stamps=clock['stamps']
            events=[json.loads(s) for s in (worker/'events.jsonl').read_text().splitlines()]
            end=next(e for e in events if e.get('event')=='REQUEST_END_PC_CANDIDATE' and e['request_id']==name)
            require(stamps['request_received_ns']<=stamps['worker_send_ns']<=stamps['first_token_ns']<=
                end['monotonic_ns']<=stamps['worker_result_ns']<=stamps['checked_ns'],
                'result/answer was exposed before durable END returned')
            require(clock['answer_source']=='MODEL' and clock['candidate_check']['status']==clock['final_check']['status']=='pass',
                'final answer not a model+checker result')
        shutil.copytree(worker,target/mode)
        copied.extend(dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                      for p in (target/mode).iterdir() if p.is_file())
    strict,request=reports['strict'],reports['request']
    for key in ('actual_cpu_permits','actual_cpu_weight_loads','owner_checks','health_checks','native_identity','libraries'):
        require(strict[key]==request[key],'A/B workload/safety/identity mismatch: '+key)
    require(strict['actual_cpu_permits']==2880 and strict['journal_rows']==2962 and request['journal_rows']==82,
        'A/B actual counts differ')
    for index,name in enumerate(('app_R0','app_hit')):
        sr=read(OUT/'run-strict-v2-02'/name/'result.json');qr=read(OUT/'run-request-v2-02'/name/'result.json')
        ordinary_comparison(sr,qr)
        a=strict['timing_PC_ONLY'][index];b=request['timing_PC_ONLY'][index]
        timings.append(dict(id=name,domain='PC_ONLY_ONE_PAIR_SAME_FROZEN_INPUT',
            strict_first_token_s=a['TTFT_app_ms']/1000,request_first_token_s=b['TTFT_app_ms']/1000,
            strict_validated_answer_s=a['complete_app_ms']/1000,request_validated_answer_s=b['complete_app_ms']/1000,
            validated_answer_delta_s=(a['complete_app_ms']-b['complete_app_ms'])/1000,
            BOARD='NOT_TESTED',board_expected_saving_s=None))
    faults=[]
    for kind,tag in [('begin_fsync','fail-begin-v2-01'),('end_fsync','fail-end-v2-01'),('health_submit','fail-health-v2-01')]:
        folder=OUT/('run-'+tag);failure=read(folder/'FAILURE.json');close=read(folder/'CPU_FAILURE_CLOSE.json')
        require(failure['fault_actually_injected'] is True and failure['validated_answers']==[] and
            close['exit_code']==2 and close['normal_close'] is False and close['forced_signal'] is False and
            close['platform_released'] is False,'real native fault was not isolated/cooperatively exited')
        private=Path(build['workspace'])/('run-'+tag)/'worker'
        stdout=[json.loads(s) for s in (private/'stdout.jsonl').read_text().splitlines()]
        terminals=[r for r in stdout if r.get('type') in ('result','error')]
        last=terminals[-1] if terminals else None
        if kind=='begin_fsync':require(failure['permission_runs']==0 and last is None,'BEGIN failure started native work')
        if kind=='end_fsync':require(failure['permission_runs']==1440 and failure['native_status']=='OK' and
            failure['native_state_cleared'] is True and failure['native_cpu_completed']==1440,'END failure proof differs')
        if kind=='health_submit':
            require(failure['permission_runs']==0 and 'fresh health failure' in failure['root_boundary_failure'] and
                failure['original_exception_cause']=='policy response is not a model baseline','masked health cause was not preserved/corrected')
            require(last and last['status']=='ERROR' and last['state_cleared_before_response'] is True and
                last['bridge']['a12_route']['pc_started_calls']==last['bridge']['a12_route']['pc_verified_completions']==0,
                'health refusal forwarded CPU work')
        rejected=audit(private,OUT/'BUILD-v2.json')
        require(rejected['status']=='REJECTED_OR_INCOMPLETE_RETAIN_OWNER' and not rejected['release_allowed'] and
                not rejected['replay_allowed'],'failed native transcript granted authority')
        faults.append(dict(kind=kind,runtime_failure=failure,cooperative_CPU_close=close,audit=rejected,
            forensic_last_native_status=last.get('status') if last else None,
            forensic_actual_cpu_completed=last.get('bridge',{}).get('a12_route',{}).get('pc_verified_completions') if last else 0,
            accepted_by_runtime=False))
        shutil.copytree(private,target/tag)
    save(OUT/'FINAL_NATIVE_CHECKS.json',dict(status='PASS_REAL_PC_NATIVE_REQUEST_JOURNAL_AND_FAILURE_FENCES',
        domain=DOMAIN,audits=audits,A_B_PC_only=timings,actual_cpu_calls_per_mode=2880,
        owner_checks_per_mode=strict['owner_checks'],health_checks_per_mode=strict['health_checks'],
        journal_rows=dict(strict=2962,request=82),journal_bytes=dict(strict=strict['journal_bytes'],request=request['journal_bytes']),
        result_delivery_after_END_proven=True,faults=faults,copied_final_transcripts=copied,
        statistical_scope='ONE_FINAL_PAIR_PER_MODE_OLDER_DEVELOPMENT_RUNS_RETAINED_NOT_POOLED',
        PL_calls=0,BOARD='NOT_TESTED',board_latency_saving_s=None,board_CMA_improvement=None,
        original_resource_probe_changed=False,overall_goal_complete=False))
    print(json.dumps(dict(status='PASS_FINAL_NATIVE_SCOPE',PC_timings=timings,real_fault_cases=3,
        original_resource_probe_changed=False,BOARD='NOT_TESTED',overall_goal_complete=False),indent=2))


if __name__=='__main__':main()
