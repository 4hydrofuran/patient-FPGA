"""Verify evidence, immutable history and documentation merge before sealing TT10-01."""
import json,shutil
from tt10_01_common import ROOT,OUT,FROZEN,j,save,sha


def main():
    assert j(OUT/'SUMMARY.json')['task01_complete']
    board=j(OUT/'BOARD_AUDIT.json');assert board['task01_complete'] and board['actual_PL_calls']<=5000
    for name in ('contracts_final','config_final','analyze_01','closeout_01','build_arm_01','build_pc_03','pc_04','component_01','cancel_01'):
        assert j(OUT/'logs'/(name+'.json'))['exit_code']==0
    assert j(OUT/'board_01/receipt.json')['payload_sent'] is False
    assert j(OUT/'board_02/receipt.json')['exit_code']==0
    assert j(OUT/'CANCEL.json')['normal_exit']==0 and j(OUT/'BAD_CONFIG.json')['exit_code']==2
    for rel,pin in j(OUT/'PROTECTED_BEFORE.json').items():assert sha(ROOT/rel)==pin
    previous={}
    for name in ('20261024-cpu-opt-00-v1','20261024-cpu-opt-01-integrated-v1','20261024-cpu-opt-02-v1','20261024-ttft10-plan-v1','20261024-ttft10-00-v1'):
        root=OUT.parent/name;pins=j(root/'SEAL.json')['files']
        for rel,row in pins.items():
            p=(root/rel).resolve();assert p.is_relative_to(root.resolve())
            if isinstance(row,str):assert sha(p)==row
            else:assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        previous[name]=dict(status='PASS_ALL_SEALED_FILES_UNCHANGED',files=len(pins))
    for rel,row in j(OUT/'READBACK_FILES.json').items():
        p=OUT/'readback-v1'/rel;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    for rel,row in j(FROZEN/'SOURCE_PINS.json').items():assert sha(ROOT/rel)==row['sha256']
    derived=j(OUT/'DERIVATION-03.json')
    for name,pin in derived['sources'].items():assert sha(OUT/'source-03'/name)==pin
    assert derived['math_sources_unchanged']
    assert sha(ROOT/'runtime/qwen35_w4a8/a12/tt10_01/prefix_cache.hpp')==derived['sources']['prefix_cache.hpp']
    assert sha(OUT/'build-arm/qwen35-a12')==j(OUT/'PACKAGE-02.json')['native_sha256']
    tools={};source=OUT/'source-final';source.mkdir()
    paths=list((ROOT/'platform/qwen35/a12').glob('tt10_01_*'))
    paths.extend([ROOT/'runtime/qwen35_w4a8/a12/tt10_01/prefix_cache.hpp',ROOT/'design/qwen35/A12_TT10_01_PREFIX_STATE.md'])
    for p in sorted(paths):
        if not p.is_file():continue
        if p.suffix=='.py':compile(p.read_text(encoding='utf-8'),str(p),'exec')
        rel=p.relative_to(ROOT).as_posix();dest=source/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        assert sha(p)==sha(dest)
        tools[rel]=dict(bytes=p.stat().st_size,sha256=sha(p),snapshot=dest.relative_to(OUT).as_posix())
    save(OUT/'SOURCE_FINAL_PINS.json',tools)
    docs=['docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md','docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md',
          'docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/PROJECT_STATUS.json','docs/handoffs/A_A12_TT10_01_20261025.json']
    for rel in docs:
        raw=(ROOT/rel).read_bytes();dest=OUT/'after-docs'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:f.write(raw)
        before=OUT/'before-closeout'/rel
        if before.exists() and rel not in ('docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md','docs/PROJECT_STATUS.json'):
            assert raw.endswith(before.read_bytes()),'prior docs overwritten: '+rel
    before=j(OUT/'before-closeout/docs/PROJECT_STATUS.json');after=j(OUT/'after-docs/docs/PROJECT_STATUS.json')
    assert {k:v for k,v in after.items() if k!='a12_ttft10_01_20261025'}==before
    assert after['a12_ttft10_01_20261025']['task01_complete']
    quality=j(OUT/'SUMMARY.json')['PC_model_answer_rejected_and_template_fallback']
    assert [r['id'] for r in quality]==['V07','V08']
    save(OUT/'FINAL_CHECK.json',dict(status='PASS_TT10_01_EVIDENCE_HISTORY_AND_DOCS',previous=previous,
        protected_sources_unchanged=True,concurrent_A13_docs_preserved=True,quality_rejections_preserved=True,
        user_pause_and_auth_failure_preserved=True,default_backend_changed=False,actual_model_settings='unknown',
        actual_PL_calls=board['actual_PL_calls'],TTFT10_goal=board['TTFT10_goal']))
    pins={p.relative_to(OUT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
        and p.name!='SEAL.json' and p.relative_to(OUT).as_posix()!='logs/final_check_01.json'}
    save(OUT/'SEAL.json',dict(status='SEALED_TT10_01_PREFIX_IMPLEMENTATION_NUMERICAL_BOARD_FAILURES',files=pins,tools=tools,
        excluded='Seal itself, Python bytecode caches, reserved final_check_01 receipt; receipt records completion/seal SHA'))
    print(json.dumps(dict(status='PASS_TT10_01_FINAL_INTEGRITY',sealed_files=len(pins),seal_sha256=sha(OUT/'SEAL.json'))))


if __name__=='__main__':main()
