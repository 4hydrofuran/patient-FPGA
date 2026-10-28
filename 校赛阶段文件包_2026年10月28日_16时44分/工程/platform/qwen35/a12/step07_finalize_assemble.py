"""Bind immutable policy and BOARD template into reviewable exact scripts."""
import ast
import json
from pathlib import Path
from common import ROOT,sha,save

OUT=ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1'


if __name__=='__main__':
    e=json.loads((OUT/'EXPECTED.json').read_text(encoding='utf-8'))
    policy=ROOT/'platform/qwen35/a12/step07_finalize_policy.py'
    board=ROOT/'platform/qwen35/a12/step07_finalize_board.py'
    text=policy.read_text(encoding='utf-8')+'\n'+board.read_text(encoding='utf-8')
    for mode in ('preflight','execute'):
        body=text+'\nmain('+repr(mode)+','+repr(e)+')\n'
        ast.parse(body);p=OUT/(mode+'_reviewed.py')
        with p.open('x',encoding='utf-8',newline='\n') as f:f.write(body)
    save(OUT/'SCRIPT_PINS.json',dict(policy_sha256=sha(policy),board_template_sha256=sha(board),
        preflight_sha256=sha(OUT/'preflight_reviewed.py'),execute_sha256=sha(OUT/'execute_reviewed.py'),
        scope='FINALIZE_ONLY_ZERO_NEW_COMPUTATION',signal='EXACT_PIDFD_SIGKILL_ONLY_AFTER_FULL_QUIESCENCE',
        authorization='User2026-10-24 prioritize resolving this retained owner; no time limit, no scope growth'))
    print('Exact read-only and execution scripts prepared; no board contact')
