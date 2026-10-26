"""Final local evidence and documentation integrity check for CPU01B."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1'


def j(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


if __name__=='__main__':
    for name in ('pc_03.json','equivalence_02.json','import_01.json','package_01.json','analyze_01.json','contracts_final.json','config_final.json','closeout_01.json'):
        assert j(OUT/'logs'/name)['exit_code']==0,name
    before=j(OUT/'before-docs/docs/PROJECT_STATUS.json');after=j(OUT/'after-docs/docs/PROJECT_STATUS.json')
    assert {k:v for k,v in after.items() if k!='a12_cpu01b_20261024'}==before
    for path in (OUT/'before-docs').rglob('*.md'):
        relative=path.relative_to(OUT/'before-docs')
        if relative.as_posix()!='docs/A12_CPU_OPTIMIZATION_PLAN_20261024.md':
            assert (OUT/'after-docs'/relative).read_bytes().endswith(path.read_bytes())
    assert after['a12_cpu01b_20261024']['peer01A_03_changed'] is False
    assert after['a12_cpu01b_20261024']['default_FPGA_enabled'] is False
    audit=j(OUT/'BOARD_AUDIT.json');assert audit['real_PL_calls']==6480
    account=j(OUT/'ACCOUNTING.json')
    pre=account['profiles']['s2/natural_profile']['accounting']['prefill']
    dec=account['profiles']['s2/natural_profile']['accounting']['decode']
    assert pre['calls']==1008 and dec['calls']==432
    for data in (pre,dec):
        assert abs(sum(data['manager_exclusive_ms'].values())-data['manager_wall_ms'])<1e-6
        assert data['channel_client_scheduling_remainder_ms'] is not None
    raw=j(OUT/'on/readback-v1/run-v1/s2/natural_profile/management-profile.json')
    names=set(pre['manager_exclusive_ms'])-{'unclassified_manager'}
    independent={phase:{name:0 for name in names} for phase in ('prefill','decode')}
    for row in raw['rows']:
        phase=row.get('model_phase')
        if phase not in independent:continue
        unions=[]
        for name in names:
            intervals=sorted((a,b) for label,a,b,cpu in row['spans'] if label==name)
            merged=[]
            for a,b in intervals:
                if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
                else:merged.append((a,b))
            independent[phase][name]+=sum(b-a for a,b in merged)
            unions.extend((a,b,name) for a,b in merged)
        unions.sort()
        assert all(a[1]<=b[0] for a,b in zip(unions,unions[1:])), 'Claimed exclusive groups overlap'
    for phase,data in (('prefill',pre),('decode',dec)):
        for name,ns in independent[phase].items():assert abs(ns/1e6-data['manager_exclusive_ms'][name])<1e-6
    assert not list((OUT/'off/readback-v1').rglob('management-profile.json'))
    with (OUT/'worktree-after.txt').open('wb') as stream:
        subprocess.run(['git','status','--porcelain=v1','--untracked-files=normal'],cwd=ROOT,stdout=stream,check=True)
    result=dict(status='PASS_CPU01B_FINAL_INTEGRITY',previous_global_fields_preserved=True,
        native_phase_counts=dict(prefill=1008,decode=432),real_PL_calls=6480,
        equation='manager exclusive siblings = measured manager wall',default_FPGA_enabled=False,A12_step11='PENDING',
        actual_model_settings='unknown',subagents=0)
    with (OUT/'FINAL_CHECK.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    files={p.relative_to(OUT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*'))
           if p.is_file() and '__pycache__' not in p.parts and p.name!='SEAL.json'
           and p.relative_to(OUT).as_posix()!='logs/final_check_01.json'}
    tools={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
           for p in sorted((ROOT/'platform/qwen35/a12').glob('cpu01b_*.py'))}
    tools['platform/qwen35/a12/test_cpu01b.py']=dict(bytes=(ROOT/'platform/qwen35/a12/test_cpu01b.py').stat().st_size,
                                                   sha256=sha(ROOT/'platform/qwen35/a12/test_cpu01b.py'))
    with (OUT/'SEAL.json').open('x',encoding='utf-8') as stream:
        json.dump(dict(status='SEALED_CPU01B_BOUNDED_BOARD_DIAGNOSTICS',files=files,tools=tools,
            excluded='SEAL.json and its in-progress final_check receipt; outer receipt records both identities.'),stream,indent=2);stream.write('\n')
    print(json.dumps(dict(result,sealed_files=len(files),seal_sha256=sha(OUT/'SEAL.json'))))
