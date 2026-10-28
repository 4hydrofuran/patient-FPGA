"""Package isolated A12 candidate; preserves all prior artifacts and global defaults."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from common import ROOT,EVIDENCE,CONTRACT,sha,save


def main(out):
    out=Path(out);out.mkdir(exist_ok=False,parents=True)
    arm=json.loads((EVIDENCE/'ARM_BUILD_FINAL.json').read_text())
    def copy(src,relative):
        target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
    for name,row in arm['files'].items():
        source=Path(row['path']);assert sha(source)==row['sha256']
        target=name+'.0' if name in ('libllama.so','libggml.so','libggml-base.so','libggml-cpu.so') else name
        copy(source,'bin/'+target)
    for p in (EVIDENCE/'source-v4').iterdir():
        if p.is_file():copy(p,'source/'+p.name)
    for p in (ROOT/'platform/qwen35/a12').glob('*'):
        if p.is_file():copy(p,'platform/qwen35/a12/'+p.name)
    for p in (ROOT/'runtime/qwen35_w4a8/a12').glob('*'):
        if p.is_file():copy(p,'runtime/qwen35_w4a8/a12/'+p.name)
    for p in (ROOT/'contracts/qwen35').iterdir():
        if p.is_file():copy(p,'contracts/qwen35/'+p.name)
    for name in ('BASELINE.json','ACCEPTANCE.json','RESOURCE_CALL_BUDGET.json','ARM_BUILD_FINAL.json',
                 'CANONICAL_COMPARISON.json','TRACE_AUDIT.json','graph-v2/SUMMARY.json','control-v1/SUMMARY.json',
                 'native-gate/SUMMARY.json','supervisor_01.json','adapter_02.json','window_01.json'):
        copy(EVIDENCE/name,'evidence/'+name)
    copy(ROOT/'system_qwen35/app/native_pl.py','system_qwen35/app/native_pl.py')
    # Keep exact native dependency headers/control helpers in the same relative project layout.
    for name in ('managed_lock.hpp',):copy(ROOT/'platform/qwen35/a11'/name,'platform/qwen35/a11/'+name)
    for name in ('accelerator_release_gate_v2.py','isolated_idle_policy.py','kernel_log_gate.py'):
        copy(ROOT/'platform/qwen35/a10'/name,'platform/qwen35/a10/'+name)
    copy(ROOT/'hw/linear_A/KERNEL_SOURCE.json','KERNEL_SOURCE.json')
    copy(ROOT/'release/a07_b04_v3/artifacts/w4a8.xclbin','w4a8.xclbin')
    copy(ROOT/'platform/qwen35/a12/selftest.py','tests/selftest.py')
    bundle=ROOT/'evidence/mlp_board_A/20261023-compute-acceptance-v1/bundle-v2'
    cfg=json.loads((bundle/'trial-config.json').read_text());cfg.update(allow_device_access=False,
        kernel_source='../KERNEL_SOURCE.json',deployment_profile='profile.pending.json',xclbin_path='../w4a8.xclbin')
    save(out/'config/backend.pending.json',cfg)
    profile=json.loads((bundle/'trial-profile-template.json').read_text())
    full=next(p for p in json.loads((EVIDENCE/'RESOURCE_CALL_BUDGET.json').read_text())['profiles'] if p['scope']=='all')
    profile.update(status='A12_PENDING_FRESH_BOARD_REVIEW_NOT_AUTHORIZED',
        trial_bo_limit_bytes=full['explicit_bo_limit_bytes'],a12_max_runs=full['max_successful_runs'],a12_max_loads=72)
    save(out/'config/profile.pending.json',profile)
    (out/'README.md').write_text('''# A12 无板候选，未部署

这是 01—05 的本地候选，不是板端通过或默认启用证明。公共数学、B 核和旧 A11 原件不变。
ARM64 构建通过；ARM 执行、模型 PL 数值、内存峰值和速度均 NOT_TESTED。
PC_MATH_DOUBLE 真实运行 CPU 数学并验证图消费，不能记作 FPGA_REAL。

`python3 -B tests/selftest.py` 仅检查清单/哈希/禁用配置，不加载 ARM 库。
bin 中的模型进程可作为 S1（无 SP_A12_CONFIG）或经过新窗口审查的 S2 候选。
目标资产根固定 /opt/patient-qwen；原模型/sidecar 不复制到本包。依赖现有锁定资产和匹配系统库。
XRT 候选仅面向 2.18.0。所有库置于独立目录，禁止覆盖系统库或旧默认 manifest。

设备访问默认关闭。下一步须执行 A12 06：新鲜身份/平台/资源检查、同板 S1 与加载峰值验证。
Window/OwnedWorker 提供新租约、双锁、逐次许可与保留隔离机制；实际 PL 准备、默认恢复编排和 BOARD 生命周期仍须在后续窗口联调验收。
close/deadline 不 kill；POISONED 不 unload。普通恢复和完整资源门禁通过后才可归档租约；不复制旧 review/launch。
''',encoding='utf-8')
    files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
           for p in sorted(out.rglob('*')) if p.is_file()]
    save(out/'manifest.json',dict(schema_version=1,module_type='linear',module_id='A_A12_PREBOARD_MODEL_CANDIDATE_V1',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_overlay='source and platform files are uncommitted A-owned derivations, individually hashed',
        provider='B',maintainer='A',contract_sha256=CONTRACT,authorization_included=False,
        execution_kind='CANDIDATE_NOT_EXECUTED_ON_BOARD',files=files,
        entrypoints=dict(library='bin/libsp_linear_a12_trial.so',selftest='tests/selftest.py'),
        tests=dict(pc=dict(status='PASS',evidence=['evidence/graph-v2/SUMMARY.json','evidence/control-v1/SUMMARY.json','evidence/native-gate/SUMMARY.json']),
                   cross_build=dict(status='PASS',evidence=['evidence/ARM_BUILD_FINAL.json']),
                   board=dict(status='NOT_TESTED',evidence=[]))))
    tool=ROOT/'docs/plan_qwen35/KV260_Qwen35_A_详细设计增强任务包_20261002/KV260_Qwen35_A_设计增强包_20261002/tools/verify_bundle.py'
    spec=importlib.util.spec_from_file_location('a12_actual_verify_bundle',tool);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.check_bundle(out,ROOT/'contracts/qwen35/contracts.lock')
    save(EVIDENCE/'PACKAGE_CHECK.json',dict(result,manifest_sha256=sha(out/'manifest.json'),bundle=str(out)))
    print(json.dumps(result))


if __name__=='__main__':main(ROOT/'release/a12_preboard_20261023_v1')
