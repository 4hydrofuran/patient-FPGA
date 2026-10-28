"""Final CPU02 safety/accounting replay, prior seal protection and evidence seal."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'
PRIOR=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'


def j(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(p,x):
    with p.open('x',encoding='utf-8') as stream:json.dump(x,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')


if __name__=='__main__':
    perf=j(OUT/'PERFORMANCE.json');audit=j(OUT/'BOARD_AUDIT.json');assert audit['actual_PL_calls']==9792
    before=j(OUT/'before-docs/docs/PROJECT_STATUS.json');after=j(OUT/'after-docs/docs/PROJECT_STATUS.json')
    assert {k:v for k,v in after.items() if k!='a12_cpu02_20261024'}==before
    assert after['a12_cpu02_20261024']['accepted']==perf['accepted']
    if perf['accepted']:
        assert j(OUT/'deployment_01/receipt.json')['exit_code']==0
        receipt=j(OUT/'deployment_01/stdout.txt')['deployment']
        assert receipt['program_sha256']==j(OUT/'PACKAGE.json')['native_program_sha256']
        assert receipt['fresh_no_users_gate'] and receipt['normal_restore'] and not receipt['default_backend_changed']
    for p in (OUT/'before-docs').rglob('*.md'):
        rel=p.relative_to(OUT/'before-docs')
        if rel.as_posix()!='docs/A12_CPU_OPTIMIZATION_PLAN_20261024.md':assert (OUT/'after-docs'/rel).read_bytes().endswith(p.read_bytes())
    account=j(OUT/'ACCOUNTING.json')['profiles']
    for mode in ('baseline','candidate'):
        for name,row in j(OUT/mode/'READBACK_FILES.json').items():
            p=OUT/mode/'readback-v1'/name;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        total=0
        for case in ('diag_exact','short_plain','natural_plain','natural_plain_2','natural_profile'):
            root=OUT/mode/'readback-v1/run-v1/s2'/case;raw=j(root/'management-profile.json');clock=j(root/'client-timing.json')
            submits=[r for r in raw['rows'] if r.get('permit',{}).get('phase')=='submit']
            for row in submits:
                assert row['outcome']=='RETURNED'
                assert clock['begin_monotonic_ns']<=row['start_ns']<=row['end_ns']<=clock['end_monotonic_ns']
                if mode=='candidate':assert sum(label=='record.fsync' for label,*_ in row['spans'])==1
            total+=len(submits)
            if case in ('diag_exact','natural_profile'):
                data=account[mode+'/s2/'+case]['management']
                for phase in ('prefill','decode'):
                    bucket=data[phase];names=set(bucket['manager_exclusive_ms'])-{'unclassified_manager'}
                    independent={name:0 for name in names}
                    for row in submits:
                        if row['model_phase']!=phase:continue
                        intervals=[]
                        for name in names:
                            merged=[]
                            for a,b in sorted((a,b) for label,a,b,cpu in row['spans'] if label==name):
                                assert row['start_ns']<=a<=b<=row['end_ns']
                                if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
                                else:merged.append((a,b))
                            independent[name]+=sum(b-a for a,b in merged);intervals.extend(merged)
                        intervals.sort();assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:]))
                    assert abs(sum(bucket['manager_exclusive_ms'].values())-bucket['manager_wall_ms'])<1e-6
                    assert all(abs(value/1e6-bucket['manager_exclusive_ms'][name])<1e-6 for name,value in independent.items())
        assert total==4896
    metrics=j(OUT/'candidate/readback-v1/run-v1/s2/natural_profile/representation-metrics.json')
    assert metrics['retained_snapshots']<=2 and metrics['retained_payload_bytes']<=16777216 and metrics['hits']>metrics['misses']
    original=j(PRIOR/'SEAL.json');assert sha(PRIOR/'SEAL.json')==j(OUT/'INTEGRITY.json')['cpu01_seal_sha256']
    for name,row in original['files'].items():
        p=PRIOR/name;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    save(OUT/'FINAL_CHECK.json',dict(status='PASS_CPU02_FINAL_INTEGRITY_SAFETY_AND_EXCLUSIVE_REPLAY',accepted=perf['accepted'],actual_PL_calls=9792,
        per_submit_fsync_proven=True,prior_cpu01_seal_unchanged=True,concurrent_A13_status_preserved=True,
        task03_changed=False,default_FPGA_enabled=False,A12_step11='PENDING',final_task08_acceptance=False,representation_metrics=metrics))
    files={p.relative_to(OUT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='SEAL.json' and p.relative_to(OUT).as_posix()!='logs/final_check_01.json'}
    tools={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted((ROOT/'platform/qwen35/a12').glob('cpu02_*.py'))}
    save(OUT/'SEAL.json',dict(status='SEALED_CPU02_BOUNDED_WORK_AND_BOARD_RESULT',files=files,tools=tools,excluded='SEAL.json and reserved in-progress final_check receipt. Outer receipt records completion and seal SHA.'))
    print(json.dumps(dict(status='PASS_CPU02_FINAL_INTEGRITY',accepted=perf['accepted'],sealed_files=len(files),seal_sha256=sha(OUT/'SEAL.json'))))
