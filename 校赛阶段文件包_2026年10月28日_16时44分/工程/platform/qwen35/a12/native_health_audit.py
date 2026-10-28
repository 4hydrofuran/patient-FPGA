"""Reconcile small ordinary native transcripts, permits, receipts and fences."""
import json
from pathlib import Path
import shutil
import sys

from health_fence_evidence import ROOT,OUT,PRIOR,read,save,sha
from native_request_audit import audit

IDS=('app_R0','warm_prefix','app_hit')


def check(tag,*,final=False):
    directory=OUT/('run-'+tag);h=read(directory/'HEALTH_FENCE.json');m=h['monitor'][0]
    success=(directory/'RESULT.json').exists()
    report=read(directory/('RESULT.json' if success else 'FAILURE.json'))
    workspace=Path(report.get('workspace','/home/member-a/kv260-build/a12-native-request-journal-20261026-v2/run-'+tag))/'worker'
    copied=OUT/'native-transcripts-v2'/tag;copied.mkdir(parents=True,exist_ok=False)
    for p in workspace.iterdir():
        assert p.is_file() and p.stat().st_size<=16*1024**2
        shutil.copyfile(p,copied/p.name)
    # NTFS evidence mirrors do not provide Linux private-directory permissions.
    # Keep that gate intact: audit the original private WSL worker directory,
    # and require the small mirror bytes to match it exactly afterwards.
    independent=audit(workspace,PRIOR/'BUILD-v2.json')
    assert all(sha(p)==sha(workspace/p.name) for p in copied.iterdir())
    assert independent['release_allowed'] is independent['replay_allowed'] is False
    rows=[json.loads(s) for s in (copied/'events.jsonl').read_text().splitlines()]
    native=[json.loads(s) for s in (copied/'stdout.jsonl').read_text().splitlines()]
    terminals=[r for r in native if r.get('type') in ('result','cache_created')]
    assert h['board_contacted'] is False and h['no_snapshot_reuse'] is True
    assert not m['thread_alive'] and m['waiters']==0 and len(m['recent_samples'])<=64
    assert report['BOARD']=='NOT_TESTED' and report['PL_calls']==0
    assert {r['path'] for r in h['source_at_launch']}=={'platform/qwen35/a12/'+n for n in
        ('fresh_identity_io.py','health_fence.py','native_health_fence.py','native_health_run.py')}
    if final:
        assert all(sha(ROOT/r['path'])==r['sha256'] for r in h['source_at_launch']),tag
    if success:
        assert independent['status']=='COMPLETE_ACTUAL_PC_NATIVE_TRANSCRIPT',independent
        assert report['actual_cpu_permits']==independent['actual_cpu_calls']==2880
        assert m['fault'] is None and m['closed'] is True
        assert m['counters']['fences']==m['counters']['authorizations']==2958
        assert m['counters']['samples']==report['health_checks']>=2958
        assert report['owner_checks']==h['owners'][0]['fresh_identity_checks']==2959
        assert report['validated_answers']==['app_R0','app_hit']
        observed=0;last_serial=0
        for r in rows:
            if r['event']!='PERMISSION':continue
            f=r['health_observation']['pc_health_fence']
            assert f['epoch']==m['epoch'] and f['serial']>last_serial
            assert f['requested_ns']<=f['started_ns']<=f['ended_ns']<=r['monotonic_ns']
            last_serial=f['serial'];observed+=1
        assert observed==(2955 if report['journal_mode']=='strict' else 75)
        boundaries=h.get('result_boundaries',[[]])[0]
        if final:
            assert [b['completed_request'] for b in boundaries]==list(IDS)
            for b in boundaries:
                receipt=read(copied/('COMMIT-'+b['completed_request']+'.json'))
                assert b['end_record_sha256']==receipt['end_record_sha256']
                assert b['requested_ns']<=b['started_ns']<=b['ended_ns']<=b['authorized_ns']
                assert b['authorized_ns']-b['started_ns']<=m['max_age_ns']
        scope='PASS_REAL_PC_NATIVE_FRESH_HEALTH_FENCE'
    else:
        assert independent['status']=='REJECTED_OR_INCOMPLETE_RETAIN_OWNER',independent
        assert h['actually_injected'] and m['fault'] and report['validated_answers']==[]
        injection=read(directory/'INJECTION.json')
        assert injection['started_ns']<=injection['published_ns']<=injection['finished_ns']
        completed=max(r['bridge']['a12_route']['pc_verified_completions'] for r in terminals)
        if h['fault_injection']=='permit_log':
            assert completed==0 and report['permission_runs']==1 and terminals[-1]['status']=='ERROR'
            assert terminals[-1]['bridge']['a12_route']['pc_output_consumable'] is False
        else:
            assert completed==1440 and report['permission_runs']==1440 and terminals[-1]['status']=='OK'
            assert report['native_state_cleared'] is True
        closure=read(directory/'CPU_FAILURE_CLOSE.json')
        assert closure['exit_code']==2 and closure['forced_signal'] is closure['platform_released'] is False
        assert not h.get('result_boundaries',[[]])[0]
        scope='PASS_REAL_PC_INJECTED_FAULT_REFUSAL_RETAIN_OWNER'
    return dict(tag=tag,status=scope,final_source=final,original_independent_audit=independent,
        fence_counters=m['counters'],journal_rows=len(rows),copied_artifacts=[
            dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(copied.iterdir())],
        BOARD='NOT_TESTED',board_latency_saving_s=None)


if __name__=='__main__':
    tags=sys.argv[1:];assert tags
    results=[check(tag,final=tag.endswith('-02')) for tag in tags]
    save(OUT/'NATIVE_AUDIT.json',dict(status='PASS',runs=results,
        limitation='Transcript/counter reconciliation is not proof of historical fsync or real DMA isolation',
        release_allowed=False,replay_allowed=False))
    print(json.dumps([dict(tag=r['tag'],status=r['status']) for r in results],indent=2))
