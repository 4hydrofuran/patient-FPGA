"""Derive the independent CPU02 auditor, preserving the proven CPU01 auditor."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'


if __name__=='__main__':
    original=(ROOT/'platform/qwen35/a12/cpu01_analyze.py').read_text(encoding='utf-8')
    code=original.replace('20261024-cpu-opt-01-integrated-v1','20261024-cpu-opt-02-v1')
    code=code.replace("'old'","'baseline'").replace("'integrated'","'candidate'")
    code=code.replace("'old/","'baseline/").replace("'integrated/","'candidate/")
    code=code.replace('3816','4896').replace('7632','9792').replace('CPU01','CPU02').replace('task01_complete','task02_complete')
    code=code.replace("('short_plain','short_profile','natural_plain','natural_profile')","('short_plain','natural_plain','natural_plain_2','natural_profile')")
    code=code.replace("for prefix in ('short','natural'):","for prefix in ('natural',):")
    code=code.replace("board_candidate='/var/lib/kv260-a12/cpu01-integrated-20261024-v1',rollback='/var/lib/kv260-a12/health-opt-20261024-v1'", "board_candidate='/var/lib/kv260-a12/cpu02-candidate-20261024-v1',rollback='/var/lib/kv260-a12/cpu01-integrated-20261024-v1'")
    # Numerical, owner/health, metadata, lifecycle and native node equations stay
    # intact. Performance is assessed separately against a predeclared rule.
    code=code.replace("    print(json.dumps(dict(status='PASS_BOARD_CPU02_COMPATIBLE_AND_UPDATED',actual_PL_calls=actual_calls)))", "    from cpu02_performance import assess\n    assess(OUT, profiles, case_index)\n    print(json.dumps(dict(status='PASS_BOARD_CPU02_SAFETY_AND_PERFORMANCE_ASSESSED',actual_PL_calls=actual_calls)))")
    compile(code,'cpu02_analyze','exec')
    target=ROOT/'platform/qwen35/a12/cpu02_analyze.py'
    with target.open('x',encoding='utf-8',newline='\n') as stream:stream.write(code)
    progress=(ROOT/'platform/qwen35/a12/cpu01_progress.py').read_text(encoding='utf-8').replace('20261024-cpu-opt-01-integrated-v1','20261024-cpu-opt-02-v1').replace("event['mode']=='old'","event['mode']=='baseline'").replace("'short_profile','natural_plain','natural_profile'","'natural_plain','natural_plain_2','natural_profile'")
    with (ROOT/'platform/qwen35/a12/cpu02_progress.py').open('x',encoding='utf-8',newline='\n') as stream:stream.write(progress)
    design=dict(status='PREDECLARED_BEFORE_CANDIDATE_MEASUREMENT',changes=['pure UTF8/SHA cache by immutable text identity, two slots','fresh canonical lock checks via the exact held FDs','compact same-schema JSONL, persistent append FD with fresh inode/link/length checks','one fsync per record; parent directory sync at first creation'],
        unchanged=['fresh kmsg drain and sequence verification every permit','boot, lease hash, FLOCK, temperatures, memory, budgets, per-DSO replay checks','record durable before one corresponding allow reply','native binaries, task01A observer, task03, platform restoration'],
        acceptance=dict(safety='all exact numeric, permission, actual healthy observations, normal release and independent/delayed scans pass',
            permission='both prefill and decode native permission wait lower in the profiled natural sample',
            ordinary_PL='both paired natural ordinary samples have lower client TTFT and complete wall',
            CPU='ordinary natural complete wall at most 5% higher in each pair, unchanged numerical results',
            limitations='Two ordinary pairs, one profile pair, fixed baseline-then-candidate order; descriptive bounded acceptance only, final task08 balanced>=5 repeats still pending'),
        rejected_candidate='Preserve source, failures and measurements; retain CPU01 selection. No weakened fsync or fresh gate to force speed.',
        PC_bench_first_pair='Initial baseline and candidate component processes overlapped; preserved and excluded from acceptance. bench_*_02 are sequential.',actual_model_settings='unknown',subagents=0)
    with (OUT/'DESIGN.json').open('x',encoding='utf-8') as stream:json.dump(design,stream,indent=2);stream.write('\n')
    print('CPU02_AUDITOR_AND_PREDECLARED_ACCEPTANCE_READY')
