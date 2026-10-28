"""Reserve task10 evidence and preserve pre-existing state before any changes."""
import json
import shutil
import subprocess
from common import ROOT, sha, save
from step10_common import OUT

if __name__ == '__main__':
    OUT.mkdir()
    docs = ('docs/PROJECT_STATUS.json', 'docs/DESIGN_GAP.md', 'docs/DECISIONS.md',
            'docs/TEST_MATRIX.md', 'docs/AI_ASSISTANCE.md', 'docs/status/A.md',
            'docs/A12_STEP_PLAN_20261023.md')
    for name in docs:
        dest = OUT / 'before' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    for argv, name in ((['git', 'status', '--short'], 'before/worktree-status.txt'),
                       (['git', 'diff', '--stat'], 'before/worktree-diff-stat.txt')):
        r = subprocess.run(argv, cwd=ROOT, capture_output=True)
        assert r.returncode == 0
        (OUT / name).write_bytes(r.stdout)
    prior = ROOT / 'evidence/model_pl_A/20261024-step09-v1/SEAL.json'
    assert sha(prior) == '3eb2cb192e0ccf66db74cefef99421f2d6e217f349dcdb7b91ccc880d71704b9'
    save(OUT / 'START.json', dict(task='A12_STEP10', physical_domains=['PC', 'CROSS_BUILD', 'BOARD'],
         prior_seal_sha256=sha(prior), actual_model_settings='unknown',
         authorization='USER_TASK10_BOARD_READ_WRITE_SAME_LIMITS',
         reboot_power_flash_authorized=False, default_FPGA_enabled=False,
         major_unresolved_problem_stop_seconds=600, scope='BOUNDED_FAIR_PERFORMANCE_AND_BOTTLENECK'))
    print(json.dumps({'status': 'TASK10_EVIDENCE_RESERVED'}))
