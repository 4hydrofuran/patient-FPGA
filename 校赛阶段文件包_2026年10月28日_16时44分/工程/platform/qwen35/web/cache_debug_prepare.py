"""Derive a fresh cache-debug web candidate without changing model/native assets."""
import json
from pathlib import Path
import shutil
from case20_prepare import manifest

ROOT=Path(__file__).resolve().parents[3];WEB=Path(__file__).resolve().parent

def prepare(output):
    base=ROOT/'release/a12_case20_random_board_20261027_v1/case20-random-t4'
    output=Path(output).resolve()
    shutil.copytree(base,output,ignore=shutil.ignore_patterns('__pycache__','*.pyc','run-v1'))
    for kind in ('ordinary','continuous'):
        window=output/kind
        shutil.copytree(WEB/'integrated/B_601e69ca_A_case20_debug_20261027/web_gateway',window/'web_gateway',
                        dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copyfile(WEB/'continuous_sessions.py',window/'continuous_sessions.py')
        if kind=='continuous':
            p=window/'interactive_case.py'
            p.write_text(p.read_text(encoding='utf-8').replace('                coordinator.engine.answer_cache=answer_cache',
                '                coordinator.engine.answer_cache=answer_cache\n                coordinator.answer_cache=answer_cache'),encoding='utf-8')
            p=window/'web-config.json';config=json.loads(p.read_text(encoding='utf-8'))
            config['browser_profile']='/home/ubuntu/snap/firefox/common/a12-case20-debug-20261027'
            p.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'CACHE_DEBUG_SOURCE.json').write_text(json.dumps(dict(profile='UI_RANDOM_CASES_CACHE_DEBUG_V1',
        next_session_modes=['auto','hit','miss'],miss='BYPASS_ANSWER_CATALOG_REAL_MODEL',
        cached_badge='CPU/FPGA 模式 · 缓存命中',uncached_note='unchanged',
        actual_backend_for_hit=None,current_model_calls_for_hit=0,model_native_HLS_contract_unchanged=True,
        BOARD='NOT_TESTED'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest(output)
    return output

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    print(prepare(p.parse_args().output))
