"""Freeze A12 inputs and compare preserved A53 source with final A05 source."""
import json
from pathlib import Path
import shutil
import subprocess
from common import ROOT, EVIDENCE, CONTRACT, sha, save


def main():
    before = EVIDENCE / 'before'
    before.mkdir(exist_ok=False)
    paths = ['AGENTS.md', 'docs/A12_STEP_PLAN_20261023.md', 'docs/PROJECT_STATUS.json',
             'docs/DESIGN_GAP.md', 'docs/DECISIONS.md', 'docs/TEST_MATRIX.md',
             'docs/AI_ASSISTANCE.md', 'docs/status/A.md', 'modules/linear_A/manifest.json',
             'config/qwen35/selection.json', 'contracts/qwen35/contracts.lock']
    for folder in ('runtime/qwen35_w4a8', 'system_qwen35/app'):
        paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/folder).glob('*')
                  if p.is_file() and p.suffix in ('.cpp', '.hpp', '.h', '.py', '.txt', '.md')]
    hashes = {}
    for relative in paths:
        target = before/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/relative, target)
        hashes[relative] = sha(target)
    status = subprocess.run(['git','status','--short','--untracked-files=all'],cwd=ROOT,
                            capture_output=True,text=True,check=True)
    (before/'git-status.txt').write_text(status.stdout,encoding='utf-8')
    sealpath = ROOT/'evidence/mlp_board_A/20261023-compute-acceptance-v1/SEAL.json'
    seal = json.loads(sealpath.read_text())
    verified = 0
    for name, entry in seal['files'].items():
        p = ROOT/name
        if p.stat().st_size != entry['bytes'] or sha(p) != entry['sha256']:
            raise ValueError('A11 seal differs: '+name)
        verified += 1
    current = Path('/home/member-a/qwen35-a05/source-v3')
    old = Path('/home/member-a/kv260-build/ra02-coordinator/work/01791005999565534417-A-a07-a53-origin-v2-d20534d2')
    source_checks = {}
    # Actual preserved input inventory is discovered, not presumed a Git checkout.
    snapshot = old/'inputs'
    for key in ('src/llama-graph.cpp','ggml/src/ggml-cpu/ops.cpp','include/llama.h'):
        p = current/key
        candidates = list(snapshot.rglob(Path(key).name))
        source_checks[key] = dict(current_sha256=sha(p), archived_matches=[
            dict(path=str(q),sha256=sha(q),equal=sha(q)==sha(p)) for q in candidates])
    artifact_files = [old/'s1/qwen35-s1', old/'s1/libsp_linear_cpu.so',
                      *[old/'llama/bin'/n for n in ('libllama.so','libggml.so','libggml-base.so','libggml-cpu.so')]]
    # A07 compile input snapshot is retained; current A12 entry must also include request_profile.cpp.
    report = dict(status='PASS_BASELINE_FROZEN_PC', domain='PC', A11_sealed_files_verified=verified,
                  A11_seal_sha256=sha(sealpath), contract_sha256=CONTRACT,
                  before=hashes, preserved_arm_artifacts={str(p):sha(p) for p in artifact_files},
                  source_checks=source_checks, source_is_git_checkout=False,
                  board='NOT_TESTED', settings='unknown',
                  inspection_failures=[
                      'Nonexistent guessed backend paths were read-only discovery errors; corrected via file inventory.',
                      'source-v3 has no .git; use fixed upstream commit and source hashes instead of git rev-parse.',
                      'Old full ELF JSON was too large for console; use parsed dependency summaries.'])
    save(EVIDENCE/'BASELINE.json',report)
    m=json.loads((ROOT/'models/sidecar_A/qwen35-v1/manifest.json').read_text())
    save(EVIDENCE/'ACCEPTANCE.json',dict(contract_sha256=CONTRACT,
        model_revision='2fc06364715b967f1860aea9cf38778875588b17',
        runtime_commit='81e39ad34368329b5db77620721510fd91107e80',
        model_sha256=sha(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),
        sidecar_manifest_sha256=sha(ROOT/'models/sidecar_A/qwen35-v1/manifest.json'),
        target_tensors=[dict(id=e['id'],layer=e['layer'],op=e['op'],N=e['N'],K=e['K']) for e in m['entries']],
        operator_tolerance=dict(atol=1e-4,rtol=1e-5), graph_tolerance=dict(atol=.002,rtol=.0002),
        fixed_tokens=[1,2,3,4,5,6,7,8,9],teacher_tokens=[10,11], sampling='GREEDY_OR_FIXED_TEACHER',
        modes=['S1_ALL_W4A8_CPU','S2_SELECTED_PL_REMAINDER_S1'],
        non_target_schedule='A05_FINAL_STABLE_PROJECTIONS_AND_ATTENTION',fallback='disabled'))
    print(json.dumps(dict(status=report['status'],A11_verified=verified,source_checks=source_checks)))


if __name__=='__main__':main()
