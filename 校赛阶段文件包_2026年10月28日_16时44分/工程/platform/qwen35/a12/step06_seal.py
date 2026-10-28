"""Verify historical protected sets, snapshot governance and seal step06 evidence."""
import hashlib
import json
from pathlib import Path
import shutil
from common import ROOT,sha,save
from step06_prepare import OUT


def main():
    # No archive is trusted just because a previous command exited successfully.
    audit=json.loads((OUT/'AUDIT.json').read_text(encoding='utf-8'))
    assert audit['hardware_submissions']==0 and audit['PL_numeric']=='NOT_TESTED'
    for n in ('contracts_postdocs','config_postdocs','utf8_review'):
        assert json.loads((OUT/(n+'.json')).read_text(encoding='utf-8'))['exit_code']==0
    preserved=[]
    for folder in ('evidence/mlp_board_A/20261023-compute-acceptance-v1',
                   'evidence/model_pl_A/20261023-preboard-v1'):
        p=ROOT/folder/'SEAL.json';m=json.loads(p.read_text(encoding='utf-8'));fail=[]
        for name,v in m['files'].items():
            q=ROOT/name
            if not q.is_file() or q.stat().st_size!=v['bytes'] or sha(q)!=v['sha256']:fail.append(name)
        assert not fail,fail
        preserved.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),files=len(m['files']),status='ALL_BYTES_PRESERVED'))
        print(json.dumps(preserved[-1]),flush=True)
    save(OUT/'HISTORICAL_PRESERVATION.json',preserved)
    after=OUT/'after';after.mkdir(exist_ok=False)
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
                 'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md','docs/handoffs/A_A12_STEP06_20261023.md'):
        p=after/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    sources=OUT/'source';sources.mkdir(exist_ok=False)
    for p in sorted((ROOT/'platform/qwen35/a12').glob('step06_*.py')):
        shutil.copyfile(p,sources/p.name)
    files={}
    for p in sorted(OUT.rglob('*')):
        if not p.is_file():continue
        assert not p.is_symlink()
        files[p.relative_to(ROOT).as_posix()]=dict(bytes=p.stat().st_size,sha256=sha(p))
    seal=OUT/'SEAL.json'
    save(seal,dict(status='SEALED_A12_STEP06_BOARD_CPU_S1_WITH_LIMITATIONS_NOT_PL_ACCEPTANCE',
                  files=files,excluded=['SEAL.json','external receipt'],historical_sets=preserved))
    receipt=dict(status='SEALED',seal=seal.relative_to(ROOT).as_posix(),sha256=sha(seal),files=len(files),
        total_bytes=sum(v['bytes'] for v in files.values()),source_sha256=sha(Path(__file__)),
        argv=['python3','-B','platform/qwen35/a12/step06_seal.py'],cwd=str(ROOT),exit_code=0)
    save(OUT.parent/'20261023-step06-v1-receipt.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
