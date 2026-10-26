"""Prepare additive CPU-only target assets/runtime, no board contact."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
from common import ROOT,sha,save

OUT=ROOT/'evidence/model_pl_A/20261023-step06-v1'


def main():
    sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
    from kernel_log_gate import KernelLogGate
    fresh=json.loads((OUT/'preflight_02/stdout.txt').read_text())
    boot=fresh['boot_id'];old=ROOT/'evidence/mlp_board_A/20261023-compute-acceptance-v1/readback-v3/kernel.raw.txt'
    gate=KernelLogGate();accepted=gate.observe(boot,old.read_bytes().decode('utf-8'),sha(old));assert accepted['allowed']
    result=gate.observe(boot,fresh['kernel_raw']);save(OUT/'KERNEL_PREFLIGHT.json',result)
    assert result['allowed'] and fresh['kernel']=='6.8.12-a10irq2'
    assert fresh['scans'][-1]['no_users_gate'] and not fresh['module_present'] and not fresh['active_lease_exists']
    assert not any(fresh['locks'].values()) and fresh['gdm_state']=='active' and fresh['fpga_state']=='operating'
    assert all(r['matches'] for r in fresh['library_pins'].values())
    for root in fresh['assets'].values():assert not any(root.values()),'existing target assets need separate reconciliation'
    before=OUT/'before';before.mkdir(exist_ok=False)
    for relative in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
                     'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md'):
        p=before/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,p)
    sources={}
    asset_names=['artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf',
                 'artifacts/qwen35-0.8b/source/chat_template.jinja','models/model.lock.json',
                 'quant/qwen35_tensor_map.json','models/sidecar_A/qwen35-v1/manifest.json']
    asset_names += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'modules/linear_A').glob('cpu*config.json')]
    sidecar=json.loads((ROOT/'models/sidecar_A/qwen35-v1/manifest.json').read_text())
    accepted=json.loads((ROOT/'evidence/model_pl_A/20261023-preboard-v1/ACCEPTANCE.json').read_text())
    assert sha(ROOT/asset_names[0])==accepted['model_sha256']
    pins=json.loads((ROOT/'evidence/model_pl_A/20261023-preboard-v1/FINAL_INPUTS.json').read_text())
    assert all(sha(ROOT/name)==pin for name,pin in pins.items())
    for entry in sidecar['entries']:
        for row in entry['files'].values():
            p=ROOT/'models/sidecar_A/qwen35-v1'/row['file']
            assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
            asset_names.append(p.relative_to(ROOT).as_posix())
    for name in asset_names:sources['assets/'+name]=ROOT/name
    package=ROOT/'release/a12_preboard_20261023_v1'
    for p in (package/'bin').iterdir():
        if 'a12_trial' in p.name:continue # No FPGA backend in the CPU-only runtime.
        sources['runtime/'+p.name]=p
    sources['control/accelerator_release_gate_v2.py']=ROOT/'platform/qwen35/a10/accelerator_release_gate_v2.py'
    sources['control/kernel_log_gate.py']=ROOT/'platform/qwen35/a10/kernel_log_gate.py'
    sources['control/step06_cpu.py']=ROOT/'platform/qwen35/a12/step06_cpu.py'
    sources['control/requests.json']=OUT/'requests.json'
    manifest=dict(schema='A12_STEP06_CPU_ASSETS_V1',boot_id=boot,kernel=fresh['kernel'],
        machine_sha256=fresh['machine_sha256'],runtime_root='/var/lib/kv260-a12/step06-20261023-v1',
        asset_root='/opt/patient-qwen',compute='CPU_REFERENCE_ONLY',PL_submissions_allowed=0,
        files={name:dict(bytes=p.stat().st_size,sha256=sha(p)) for name,p in sources.items()},
        max_temperature_mC=55000,min_available_kib=1048576,min_CmaFree_kib=32768,
        kernel_baseline_sha256=fresh['kernel_sha256'])
    save(OUT/'deployment-manifest.json',manifest)
    archive=OUT/'cpu-assets.tar'
    with tarfile.open(archive,'w') as tar:
        for name,p in sources.items():tar.add(p,arcname=name,recursive=False)
        tar.add(OUT/'deployment-manifest.json',arcname='deployment-manifest.json',recursive=False)
        # Exact reviewed raw baseline for continuity, not a waiver for new diagnostics.
        baseline=OUT/'kernel-baseline.raw.txt';baseline.write_text(fresh['kernel_raw'])
        tar.add(baseline,arcname='kernel-baseline.raw.txt',recursive=False)
    save(OUT/'UPLOAD.json',dict(archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),
        remote_upload='/home/ubuntu/a12-step06-20261023-v1.tar',manifest_sha256=sha(OUT/'deployment-manifest.json')))
    print(json.dumps(dict(status='CPU_ONLY_PACKAGE_READY',files=len(sources),archive_bytes=archive.stat().st_size)))


if __name__=='__main__':main()
