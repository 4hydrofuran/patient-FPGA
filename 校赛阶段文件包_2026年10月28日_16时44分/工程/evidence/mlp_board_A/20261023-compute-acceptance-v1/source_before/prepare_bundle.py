"""PC-only candidate package. Fresh boot, baseline and approval are NOT embedded."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from mlp_policy import digest,verify_bundle,SCOPE


def main(out):
    ev=ROOT/'evidence/mlp_board_A/20261023-integration-v1'
    prep=ROOT/'evidence/mlp_board_A/20261023-preparation-v1'
    out.mkdir(parents=True,exist_ok=False)
    def copy(src,name=None,pin=None):
        if pin and digest(src)!=pin:raise ValueError('source differs: '+str(src))
        dst=out/(name or src.name);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    for name in ('accelerator_release_gate_v2.py','isolated_idle_policy.py','idle_board_trial.py',
                 'kernel_log_gate.py','xrt_worker_boundary.py'):
        copy(ROOT/'platform/qwen35/a10'/name)
    for name in ('mlp_manager_entry.py','mlp_worker.py','mlp_engine.py','mlp_policy.py','manager_support.py'):
        copy(ROOT/'platform/qwen35/a11'/name)
    for name in ('mlp_manager.py','mlp_base.py','mlp_kernel_gate.py','mlp_boundary_v2.py'):
        copy(ev/'management-v1'/name)
    # Keep the historical derived manager immutable; update only this candidate.
    manager=out/'mlp_manager.py';body=manager.read_text(encoding='utf-8')
    if body.count('2154496')!=1:raise ValueError('historical BO peak seam differs')
    manager.write_text(body.replace('2154496','2162688'),encoding='utf-8')
    copy(ev/'backend-v1/libsp_linear_a11_trial.so',pin='4d30d6dfb744aa47e0ce4a3faf5a6f685a1ee88fbeb6fe5c241c2dbed7990e38')
    copy(ev/'quant-v1/liba11_quant.so',pin='3b911842a033c4863e45e368822e154ab103727a22d67151d12f787bae380215')
    copy(ev/'overlay-v1/a11-mlp.bit.bin',pin='d1003cf2c451c06ff8b4acf50eb62400036e3ce959466543fb57c7fd67e82aa5')
    copy(ev/'overlay-v1/a11-mlp.dtbo',pin='eea4d4f5cbf4f0ffca53a2a49ed529e0b95c69807908d7b656dc3616b0e4536b')
    copy(ROOT/'release/a07_b04_v3/artifacts/w4a8.xclbin',pin='bdcb66ca69279e0109928d7b32c3ea0325f617a267e1869636944ba3c193b5fa')
    copy(ROOT/'platform/local/a10-isolated-single-20261023-v1/zocl.refcount.ko',pin='388c45a0edefe221615d71ea948de00d0ef68190bdd8497b053dddf788f72b2c')
    copy(ROOT/'hw/linear_A/KERNEL_SOURCE.json','KERNEL_SOURCE.json')
    copy(ROOT/'evidence/board_platform/A10_20261023_isolated_single_v1/audit_01.json','prior-a10-audit.json')
    vectors=prep/'vectors-v2';copy(vectors/'manifest.json','vectors/manifest.json')
    plan=json.loads((vectors/'manifest.json').read_text())
    # Only frozen inputs and independently verified Y references, no test mocks,
    # compiler, full model, system libraries, credentials or old authorization.
    for weight,entry in plan['weights'].items():
        for name,meta in entry['files'].items():
            copy(vectors/'inputs'/weight/name,'vectors/inputs/'+weight+'/'+name,pin=meta['sha256'])
    for case,entry in plan['cases'].items():
        for name,meta in entry['files'].items():
            copy(vectors/'inputs'/case/name,'vectors/inputs/'+case+'/'+name,pin=meta['sha256'])
        meta=entry['golden']['y.bin'];copy(vectors/'pc_reference'/case/'y.bin',
                                        'vectors/pc_reference/'+case+'/y.bin',pin=meta['sha256'])
    def put(name,obj):(out/name).write_text(json.dumps(obj,indent=2),encoding='utf-8')
    put('shell.json',dict(shell_type='XRT_FLAT',num_pl_slots=1,num_aie_slots=0))
    put('trial-config.json',dict(api_version=1,contract_sha256=plan['contract_sha256'],
        backend_id='A_XRT_B_KERNEL_V1',fallback='disabled',allow_device_access=True,
        kernel_source='KERNEL_SOURCE.json',deployment_profile='trial-profile.json',
        xclbin_path='w4a8.xclbin',xclbin_sha256=digest(out/'w4a8.xclbin')))
    put('trial-profile-template.json',dict(status='A11_BOUNDED_TRIAL_AUTHORIZED_NOT_ACCEPTED',
        source_xo_sha256='96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23',
        # irq2 uses 4 KiB pages. A single-page DMA allocation can bypass global
        # CMA and land above HP0's 2 GiB aperture. Request at least two pages;
        # the backend must still validate every returned physical range.
        xclbin_sha256=digest(out/'w4a8.xclbin'),trial_bo_limit_bytes=4194304,bo_charge_alignment=8192,
        kernel_build_id=0xB3030002,device_index=0,device_name=None,
        device_name_policy='fresh read /etc/xocl.txt token or confirmed absent -> edge; never guess',
        xclbin_uuid='ec6bb114-e3e0-7c8a-9194-4d75b3275325',argument_groups=[3]*6,
        argument_address_windows=[dict(base=0,span=2147483648)]*6))
    files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(out.rglob('*')) if p.is_file()}
    put('manifest.json',dict(schema='A11_MLP_BUNDLE_V1',scope=SCOPE,authorization_included=False,
        max_submissions=23,board_accepted=False,files=files))
    verify_bundle(out,digest(out/'manifest.json'))
    print(json.dumps(dict(status='PC_BUNDLE_HASH_VERIFIED_NOT_AUTHORIZED_OR_DEPLOYED',
        manifest_sha256=digest(out/'manifest.json'),files=len(files)+1,
        payload_bytes=sum(e['bytes'] for e in files.values()),explicit_bo_limit_bytes=4194304,
        expected_explicit_peak_bytes=2162688,BOARD='NOT_TESTED')))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    main(ap.parse_args().out.resolve())
