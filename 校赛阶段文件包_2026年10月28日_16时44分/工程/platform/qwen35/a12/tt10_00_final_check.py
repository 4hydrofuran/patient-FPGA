"""Verify frozen evidence and protected history, then seal this stage only."""
import hashlib
import json
from pathlib import Path
import shutil
from tt10_00_prepare import ROOT, OUT, j, save


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    assert j(OUT/'SUMMARY.json')['task00_complete']
    assert j(OUT/'BOARD_AUDIT.json')['actual_PL_calls']==9360
    for name in ('contracts_final','config_final','analyze_01','closeout_01'):
        assert j(OUT/'logs'/(name+'.json'))['exit_code']==0
    assert j(OUT/'board_03/receipt.json')['exit_code']==0
    for rel, row in j(OUT/'PROTECTED_BEFORE.json').items():
        assert (ROOT/rel).stat().st_size==row['bytes'] and sha(ROOT/rel)==row['sha256']
    previous={}
    for name in ('20261024-cpu-opt-00-v1','20261024-cpu-opt-01-integrated-v1','20261024-cpu-opt-02-v1','20261024-ttft10-plan-v1'):
        root=OUT.parent/name
        files=j(root/'SEAL.json')['files']
        for rel, row in files.items():
            path=(root/rel).resolve()
            assert path.is_relative_to(root.resolve())
            if isinstance(row,str):assert sha(path)==row
            else:assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
        previous[name]=dict(status='PASS_ALL_SEALED_FILES_UNCHANGED',files=len(files))
    for mode in ('health','cpu02'):
        for rel, row in j(OUT/mode/'READBACK_FILES.json').items():
            path=OUT/mode/'readback-v1'/rel
            assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
    # Frozen production source and native/template inputs have not drifted.
    for rel, row in j(OUT/'SOURCE_PINS.json').items():
        assert sha(ROOT/rel)==row['sha256']
    app=ROOT/'platform/qwen35/a12/tt10_00_app.py'
    for mode, version in [('health','v1'),('cpu02','v2')]:
        assert sha(app)==sha(OUT/mode/('bundle-'+version)/'platform/qwen35/a12/tt10_00_app.py')
    source=OUT/'source-final'
    source.mkdir()
    tools={}
    for path in sorted((ROOT/'platform/qwen35/a12').glob('tt10_00_*')):
        if not path.is_file() or path.suffix not in ('.py','.cs'):continue
        if path.suffix=='.py':compile(path.read_text(encoding='utf-8'),str(path),'exec')
        dest=source/path.name
        shutil.copyfile(path,dest)
        assert sha(dest)==sha(path)
        tools[path.relative_to(ROOT).as_posix()]=dict(bytes=path.stat().st_size,sha256=sha(path),snapshot=dest.relative_to(OUT).as_posix())
    save(OUT/'SOURCE_FINAL_PINS.json',tools)
    governance=['docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md','docs/status/A.md','docs/DESIGN_GAP.md',
                'docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/PROJECT_STATUS.json',
                'docs/handoffs/A_A12_TT10_00_20261024.json']
    for rel in governance:
        data=(ROOT/rel).read_bytes()
        target=OUT/'after-docs'/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(data)
        before=OUT/'before-closeout'/rel
        if before.exists() and rel not in ('docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md','docs/PROJECT_STATUS.json'):
            assert data.endswith(before.read_bytes()),'prior documentation overwritten: '+rel
    before=j(OUT/'before-closeout/docs/PROJECT_STATUS.json')
    after=j(OUT/'after-docs/docs/PROJECT_STATUS.json')
    assert {k:v for k,v in after.items() if k!='a12_ttft10_00_20261024'}==before
    assert after['a12_ttft10_00_20261024']['task00_complete']
    failures=j(OUT/'FAILURES.json')
    assert failures['BOARD_initial_postcheck_failures']==failures['BOARD_precompute_manager_refusals']==1
    assert j(OUT/'CPU02_RETRY_REVIEW.json')['safety_gate_conditions_unchanged']
    save(OUT/'FINAL_CHECK.json',dict(status='PASS_TT10_00_EVIDENCE_AND_HISTORY',actual_PL_calls=9360,
        previous=previous,production_source_pins_unchanged=True,concurrent_A13_documentation_preserved=True,
        first_postcheck_failure_preserved=True,precompute_refusal_preserved=True,all_safety_predicates_retained=True,
        real_inputs=25,cache_implemented=False,TTFT10_goal='NOT_MET_R0_BASELINE',default_FPGA_enabled=False))
    files={p.relative_to(OUT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
           for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
           and p.name!='SEAL.json' and p.relative_to(OUT).as_posix()!='logs/final_check_01.json'}
    save(OUT/'SEAL.json',dict(status='SEALED_TT10_00_BASELINES_WORKLOAD_TIMING_AND_FAILURES',files=files,tools=tools,
        excluded='SEAL itself, Python bytecode caches, and reserved final_check_01 receipt; receipt records completion and seal SHA'))
    print(json.dumps(dict(status='PASS_TT10_00_FINAL_INTEGRITY',sealed_files=len(files),seal_sha256=sha(OUT/'SEAL.json'))))


if __name__=='__main__':
    main()
