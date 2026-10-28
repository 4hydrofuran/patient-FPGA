"""Finalize partial-preparation evidence after all recorder processes have exited."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/mlp_board_A/20261023-preparation-v1'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)


def main():
    old=read(OUT/'seal_01.json')
    drift=[p for p,m in old['files'].items() if sha(ROOT/p)!=m['sha256']]
    expected=['evidence/mlp_board_A/20261023-preparation-v1/summarize_01.json']
    if drift!=expected:raise ValueError('unexpected old seal drift: '+repr(drift))
    for name,m in read(ROOT/'evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json')['files'].items():
        if sha(ROOT/name)!=m['sha256']:raise ValueError('A10 historical evidence changed: '+name)
    docs=['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md',
          'docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md']
    for name in docs:
        dest=OUT/'docs_after'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():raise ValueError('exclusive docs snapshot required')
        shutil.copyfile(ROOT/name,dest)
    read(ROOT/'docs/PROJECT_STATUS.json')
    for p in (ROOT/'platform/qwen35/a11').glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    paths=[p for p in OUT.rglob('*') if p.is_file()]
    paths.extend(p for p in (ROOT/'platform/qwen35/a11').iterdir() if p.is_file())
    files={p.relative_to(ROOT).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in paths}
    seal=dict(scope='A11 partial PC preparation and read-only board observation; no BOARD compute acceptance',
              original_seal_drift_preserved=drift,
              original_seal_cause='Recorder had reserved summarize_01.json but had not finalized it at first seal',
              correction='Seal only finalized receipts; no concurrent recorder for this command',files=files)
    save(OUT/'seal_02.json',seal)
    for name,m in read(OUT/'seal_02.json')['files'].items():
        if sha(ROOT/name)!=m['sha256']:raise ValueError('new seal verification failed')
    save(OUT/'seal_command_02.json',dict(argv=[sys.executable,'-B',*sys.argv],cwd=str(Path.cwd()),
         exit_code=0,files_verified=len(files),A10_historical_files_unchanged=88,all_a11_python_syntax='PASS',
         seal_sha256=sha(OUT/'seal_02.json'),
         note='seal and this post-verification receipt are not self-included in the file inventory'))
    print(json.dumps(dict(files_verified=len(files),A10_unchanged=True,A11='NOT_PASSED',BOARD_compute=0)))


if __name__=='__main__':main()
