"""PC-only evidence audit. This cannot mark A11 BOARD passed."""
import argparse
import ast
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from mlp_policy import digest,verify_bundle


def main(out):
    ev=ROOT/'evidence/mlp_board_A/20261023-integration-v1'
    package=ROOT/'platform/local/a11-mlp-20261023-v1'
    pin='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
    man=verify_bundle(package,pin)
    records={}
    for name in ('overlay_01','management_01','quant_engine_01','engine_tests_02','manager_tests_01',
                 'boundary_tests_02','resource_backend_01','package_01','engine_tests_03','shutdown_plan_01'):
        p=ev/(name+'.json');d=json.loads(p.read_text(encoding='utf-8'))
        assert d['exit_code']==0,name+' did not pass'
        records[name]=dict(exit_code=0,sha256=digest(p),command=d['argv'])
    for p in package.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    for name in ('mlp_manager_entry.py','mlp_worker.py','mlp_engine.py','mlp_policy.py','manager_support.py'):
        assert digest(package/name)==digest(ROOT/'platform/qwen35/a11'/name),'live source changed: '+name
    old=json.loads((ROOT/'evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json').read_text())
    for name,entry in old['files'].items():assert digest(ROOT/name)==entry['sha256'],name+' A10 changed'
    report=dict(A11='PC_PREPARED_BOARD_NOT_TESTED',A12='NOT_ELIGIBLE',board_compute_calls=0,
        package=str(package),manifest_sha256=pin,package_files=len(man['files'])+1,
        commands=records,A10_sealed_files_unchanged=len(old['files']),
        fresh_board_state=dict(boot_id='f4a2ac41-8010-43ee-ad8a-3b89e05034be',kernel='6.8.0-1036-xilinx',
            temperature_range_mC=[28583,30619],default_PL=True,zocl_present=False,active_lease=False,
            sources=['board_preflight_01.json','board_assets_01.json']),
        limits=dict(max_calls=23,max_real_shape_calls=21,planned_explicit_peak_bytes=2154496,
            explicit_bo_ceiling_bytes=4194304,temperature_stop_mC=55000,memory_reserve_KiB=1048576,
            CMA_reserve_KiB=32768,per_call_soft_timeout_ms=5000,worker_soft_deadline_s=240,
            force_kill=False,automatic_retry=False,hardware_integer_debug=None,effective_bandwidth=None),
        remaining=['normal shutdown and manual cold boot into already accepted irq2',
            'fresh boot/DT/kernel diagnostics review and package linkage check',
            'single authorized MLP lifecycle, actual numerical/timing records',
            'normal process exit/release/default restoration and independent audit'],
        P2=['hardware AXI/cycle counters','large memory coverage','long-duration stability'],
        external_source_notes=[dict(url='https://raw.githubusercontent.com/Xilinx/XRT/2024.2/src/runtime_src/core/edge/user/device_linux.cpp',
            fact='board_name consults /etc/xocl.txt first token, otherwise edge; API runtime equality still required')])
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(dict(A11=report['A11'],A12=report['A12'],passed_command_records=len(records),
                         A10_sealed_files_unchanged=len(old['files']))))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    main(ap.parse_args().out)
