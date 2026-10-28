"""Final integrity seal for combined CPU01; no new BOARD action."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'


def j(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(p,x):
    with p.open('x',encoding='utf-8') as stream:json.dump(x,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


if __name__=='__main__':
    assert j(OUT/'BOARD_AUDIT.json')['task01_complete']
    assert j(OUT/'deployment_01/receipt.json')['exit_code']==0
    deployed=j(OUT/'deployment_01/stdout.txt')
    assert deployed['deployment']['program_sha256']==j(OUT/'PACKAGE.json')['configurations'][1]['program_sha256']
    assert deployed['deployment']['fresh_no_users_gate'] and deployed['deployment']['normal_restore']
    assert not deployed['deployment']['default_backend_changed']
    before=j(OUT/'before-docs/docs/PROJECT_STATUS.json');after=j(OUT/'after-docs/docs/PROJECT_STATUS.json')
    assert {k:v for k,v in after.items() if k!='a12_cpu01_integrated_20261024'}==before
    assert after['a12_cpu01_integrated_20261024']['task01']=='COMPLETE'
    for p in (OUT/'before-docs').rglob('*.md'):
        rel=p.relative_to(OUT/'before-docs')
        if rel.as_posix()!='docs/A12_CPU_OPTIMIZATION_PLAN_20261024.md':assert (OUT/'after-docs'/rel).read_bytes().endswith(p.read_bytes())
    for mode in ('old','integrated'):
        for name,row in j(OUT/mode/'READBACK_FILES.json').items():
            p=OUT/mode/'readback-v1'/name
            assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        for side in ('s1','s2'):
            for name in ('diag_exact','short_profile','natural_profile'):
                raw=j(OUT/mode/'readback-v1/run-v1'/side/name/'management-profile.json')
                if side=='s1':
                    assert all(row['kind']=='idle' and 'permit' not in row for row in raw['rows'])
                    continue
                acc=j(OUT/'ACCOUNTING.json')['profiles'][mode+'/'+side+'/'+name]['management']
                for phase in ('prefill','decode'):
                    data=acc[phase];assert abs(sum(data['manager_exclusive_ms'].values())-data['manager_wall_ms'])<1e-6
                    labels=set(data['manager_exclusive_ms'])-{'unclassified_manager'}
                    sums={label:0 for label in labels};count=0
                    for row in raw['rows']:
                        if row.get('model_phase')!=phase:continue
                        count+=1;intervals=[]
                        assert row['outcome']=='RETURNED'
                        for label in labels:
                            parts=sorted((a,b) for n,a,b,cpu in row['spans'] if n==label);merged=[]
                            for a,b in parts:
                                assert row['start_ns']<=a<=b<=row['end_ns']
                                if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
                                else:merged.append((a,b))
                            sums[label]+=sum(b-a for a,b in merged);intervals.extend((a,b,label) for a,b in merged)
                        intervals.sort();assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])), 'exclusive spans overlap'
                    assert count==data['calls']
                    assert all(abs(ns/1e6-data['manager_exclusive_ms'][label])<1e-6 for label,ns in sums.items())
    for name,info in j(OUT/'INTEGRITY.json')['seals'].items():
        directory=ROOT/'evidence/model_pl_A'/name
        assert sha(directory/'SEAL.json')==info['seal_sha256']
        for relative,row in j(directory/'SEAL.json')['files'].items():
            p=directory/relative;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    save(OUT/'FINAL_CHECK.json',dict(status='PASS_CPU01_FINAL_INTEGRITY_AND_EXCLUSIVE_INTERVAL_REPLAY',task01='COMPLETE',board_updated=True,
        original_seals_unchanged=True,concurrent_status_preserved=True,default_FPGA_enabled=False,A12_step11='PENDING'))
    files={p.relative_to(OUT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='SEAL.json' and p.relative_to(OUT).as_posix()!='logs/final_check_01.json'}
    tools={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted((ROOT/'platform/qwen35/a12').glob('cpu01_*')) if p.is_file()}
    save(OUT/'SEAL.json',dict(status='SEALED_CPU01_COMPATIBLE_AND_BOARD_UPDATED',files=files,tools=tools,excluded='SEAL.json and its currently reserved final_check receipt. Final outer receipt records the seal identity.'))
    print(json.dumps(dict(status='PASS_CPU01_FINAL_INTEGRITY',sealed_files=len(files),seal_sha256=sha(OUT/'SEAL.json'))))
