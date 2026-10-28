"""Reconcile every development/final native window and preserve small transcripts."""
import json
from pathlib import Path
import shutil
from microbatch_evidence import ROOT,OUT,read,save,sha
from microbatch_audit import audit
from microbatch_page import COUNT,ACTIVE,REVOKED


def review(tag):
    directory=OUT/('run-'+tag);m=read(directory/'MICROBATCH.json');b=read(m['build_receipt']);w=m['workers'][0]
    workspace=Path(b['workspace'])/('run-'+tag)/'worker';success=(directory/'RESULT.json').exists()
    result=read(directory/('RESULT.json' if success else 'FAILURE.json'))
    assert sha(b['library'])==b['library_sha256']==m['adapter_sha256']
    assert sha(b['existing_cpu_library'])==b['existing_cpu_library_sha256']
    assert sha(b['existing_native'])==b['existing_native_sha256']
    final=b['revision']==5 and tag.endswith('-03')
    if final:
        assert all(sha(ROOT/r['path'])==r['sha256'] for r in m['source_at_launch'])
        assert w['all_protocol_and_observer_threads_stopped'] is True
        assert m['owner_FDs_closed_after_observer_stop']==[True] and m['partial_initialization']==[]
    assert w['worker_exit_code']==(0 if success else 2) and w['watchers_stopped'] and w['monitor_stopped']
    assert not w['monitor']['thread_alive'] and w['monitor']['waiters']==0
    independent=audit(workspace,Path(m['build_receipt']))
    assert independent['release_allowed'] is independent['replay_allowed'] is False
    native=[json.loads(line) for line in (workspace/'stdout.jsonl').read_text().splitlines()]
    terminals=[r for r in native if r.get('type') in ('result','cache_created')]
    if success:
        assert independent['status']=='COMPLETE_ACTUAL_PC_MICROBATCH_TRANSCRIPT',independent
        assert independent['actual_cpu_calls']==w['manager_reserved_jobs']==w['shared_claims']==2880
        assert independent['batch_grants']==w['grants']==2880//m['grant_size']
        assert not w['gate_before_close']&(REVOKED|ACTIVE)
        assert (w['monitor']['counters']['fences']==w['monitor']['counters']['authorizations']==
            result['permission_metrics']['calls']+3)
        assert w['monitor']['fault'] is None and result['validated_answers']==['app_R0','app_hit']
        assert [r['request_id'] for r in w['result_boundaries']]==['app_R0','warm_prefix','app_hit']
        for stamp in w['result_boundaries']:
            receipt=read(workspace/('COMMIT-'+stamp['request_id']+'.json'))
            assert stamp['end_sha256']==receipt['end_record_sha256']
            assert stamp['requested_ns']<=stamp['started_ns']<=stamp['ended_ns']<=stamp['authorized_ns']
            assert stamp['authorized_ns']-stamp['started_ns']<=250_000_000
        outcome='PASS_REAL_CPU_NATIVE_RANGE_JOURNAL_AND_RECEIPTS'
    else:
        assert independent['status']=='REJECTED_OR_INCOMPLETE_RETAIN_OWNER',independent
        assert result['validated_answers']==[] and m['injections'] and w['gate_before_close']&REVOKED
        assert w['result_boundaries']==[]
        cpu=terminals[-1]['bridge']['a12_route'];counter=cpu['pc_batch']
        assert w['shared_claims']==counter['shared_claims']==m['injections'][0]['revoke_prior_claims']
        if m['fault']=='cached_revoke':
            assert w['grants']==1 and w['manager_reserved_jobs']==72 and 0<w['shared_claims']<72
            assert cpu['pc_started_calls']<=w['shared_claims'] and cpu['cpu_run_count']<=cpu['pc_started_calls']
            assert terminals[-1]['status']=='ERROR' and cpu['pc_output_consumable'] is False
        else:
            assert w['manager_reserved_jobs']==w['shared_claims']==cpu['pc_verified_completions']==1440
            assert terminals[-1]['status']=='OK' and terminals[-1]['state_cleared_before_response'] is True
            assert (workspace/'COMMIT-app_R0.json').exists()
        closure=read(directory/'CPU_FAILURE_CLOSE.json')
        assert closure['forced_signal'] is closure['platform_released'] is False and closure['exit_code']==2
        outcome='PASS_INJECTED_REVOKE_RETAINED_NO_DELIVERY_OR_REPLAY'
    copied=OUT/'native-transcripts'/tag;copied.mkdir(parents=True,exist_ok=False)
    for p in sorted(workspace.iterdir()):
        assert p.is_file() and p.stat().st_size<=16*1024**2;shutil.copyfile(p,copied/p.name)
        assert sha(p)==sha(copied/p.name)
    return dict(tag=tag,status=outcome,final_source=final,build_revision=b['revision'],
        grant_size=m['grant_size'],manager_reserved_jobs=w['manager_reserved_jobs'],shared_claims=w['shared_claims'],
        native_final_cpu_core_count=terminals[-1]['bridge']['a12_route']['cpu_run_count'],
        native_final_started=terminals[-1]['bridge']['a12_route']['pc_started_calls'],
        native_final_verified=terminals[-1]['bridge']['a12_route']['pc_verified_completions'],
        independent_audit=independent,transcripts=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,
            sha256=sha(p)) for p in sorted(copied.iterdir())],BOARD='NOT_TESTED',PL_calls=0)


if __name__=='__main__':
    tags=sorted(p.name[4:] for p in OUT.glob('run-*') if (p/'MICROBATCH.json').exists())
    rows=[review(tag) for tag in tags]
    build=read(OUT/'BUILD-v5-reviewed.json');source=Path(build['workspace'])/'source'
    target=OUT/'build-source-final';target.mkdir(exist_ok=False)
    for p in source.iterdir():
        shutil.copyfile(p,target/p.name);assert sha(p)==sha(target/p.name)
    save(OUT/'NATIVE_REVIEW.json',dict(status='PASS',runs=rows,release_allowed=False,replay_allowed=False,
        limitation='Original private WSL transcript audit, mirrored bytes; not historical fsync or real DMA proof'))
    print(json.dumps([dict(tag=r['tag'],status=r['status']) for r in rows],indent=2))
