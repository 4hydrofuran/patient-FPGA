"""Publish bounded step06 results; keep all older stage evidence and failures."""
import json
from pathlib import Path
from common import ROOT,save
from step06_prepare import OUT


def main():
    a=json.loads((OUT/'AUDIT.json').read_text(encoding='utf-8'))
    assert a['worker_exit_code']==a['manager_exit_code']==0
    assert all(v['reserve_check'] for v in a['admission'].values())
    for n in ('contracts_final','config_final','audit_04'):
        assert json.loads((OUT/(n+'.json')).read_text(encoding='utf-8'))['exit_code']==0
    failures=[
      dict(id='prepare_01',domain='PC_TOOL',exit_code=1,problem='Text newline normalization changed historical dmesg bytes',resolution='Read kernel captures as raw bytes before UTF-8 decoding; preflight_02/prepare_02 pass; no kernel change'),
      dict(id='audit_01',domain='PC_ARM_CROSS_ISA_GRAPH',exit_code=1,problem='Fixed graph tolerance exceeded; max logit differences about 0.85 to 1.36',resolution='FAIL retained. First l00 gate/up input difference <=3.94e-6 straddles A8 1.5 boundary, q=1 vs2. Eight captured ARM/PC projection inputs independently match A04 scalar bit-exact. No math/tolerance/weights changed',status='FAIL_RETAINED_LIMITATION_NOT_SAME_BOARD_OR_PL_FAILURE'),
      dict(id='audit_02',domain='BOARD_CAPACITY_OBSERVATION',exit_code=1,problem='Initial full-model hypothetical BO plus additional64MiB reserve fails CMA margin; single projection and MLP pass',resolution='Initial scenario remains FAIL. Only three task archive files fsync/fadvise(DONTNEED), content retained. Separate resource-only v2 teacher_T8/no dumps passes same reserve. Actual BO/address/physical peak still NOT_TESTED',status='CONDITIONAL_V2_PASS_INITIAL_FAIL_RETAINED'),
      dict(id='resource_launch_01',domain='SSH_TRANSPORT',exit_code=255,problem='Authentication connection closed; empty stdout',resolution='New receipt resource_launch_02; exclusive remote output creation prevents duplicate workload; dispatched once'),
      dict(id='audit_03',domain='WINDOWS_TOOL',exit_code=1,problem='Windows default GBK cannot decode UTF-8 synthetic Chinese response',resolution='audit_04 under WSL UTF-8 passes. Final local audit uses explicit UTF-8; original receipt retained'),
    ]
    save(OUT/'FAILURES.json',failures)
    status=dict(status='PASS_STEP06_BOARD_S1_WITH_LIMITATIONS',physical_domain='BOARD',
        same_board_logits='BIT_EXACT_T8_T1_10_LOGIT_ROWS',sampled_projections='PASS_12_GROUPS_LAYERS_0_3_4_23',
        mixed_state='BIT_EXACT_T8_T1',natural=a['natural'],
        resource=a['resource'],resource_v2=a['resource_v2'],
        initial_capacity=a['initial_admission'],conditional_capacity=a['admission'],
        cross_ISA_graph='FAIL_RETAINED',same_input_reference='PASS_8_CAPTURED_INPUTS_BIT_EXACT',
        boot_id=a['boot_id'],kernel=a['kernel'],
        model_settings='unknown',subagents=0,hardware_submissions=0,
        hardware_global_count=None,PL_numeric='NOT_TESTED',board_speedup=None,
        actual_PL_BO_allocation='NOT_TESTED',full_model_physical_peak_bytes=None,
        postcheck='WORKERS_AND_MANAGERS_NORMAL_EXIT_0_NO_DEVICE_USERS_LOCKS_LEASE_ZOCL_DEFAULT_PL_GDM_UNCHANGED',
        next_step='07_NOT_STARTED_FRESH_LIVE_RESOURCE_AND_BO_ADDRESS_GATES_REQUIRED',
        board_writes=['New /opt/patient-qwen assets (previously absent)',
                      'New /var/lib/kv260-a12/step06-20261023-v1 runtime/control/results',
                      'Task upload/readback archives under /home/ubuntu',
                      'Two temporary CPU-only canonical leases archived; both locks released',
                      'Targeted fadvise of three task archives only; no content deletion'],
        contract_changed=False,model_math_changed=False,default_FPGA_enabled=False,
        report='evidence/model_pl_A/20261023-step06-v1/REPORT.md',committed=False,pushed=False)
    save(OUT/'SUMMARY.json',status)
    report='''# A12 第06步：同板 S1 基线与资源核对

结论：**PASS_STEP06_BOARD_S1_WITH_LIMITATIONS**。01—05 既有证据保持；本轮在真实 KV260 ARM64 上验证 CPU S1，07 尚未开始，A12 整体仍在进行。PL 模型消费、实际 BO 分配、硬件数值、加速比与完整物理峰值均未测；默认设备访问开关未启用。

## 实测结果

- 固定 host key/网卡地址核对设备、machine-id 摘要、boot、irq2 内核、XRT2.18 库哈希、默认 PL、GDM、温度/内存、全进程 FD/VMA、双锁及唯一租约；基线与 A11 一致。boot `8422f92f-d01f-4849-ad19-6e66b640a9ad`，内核 `6.8.12-a10irq2`。内核日志与既有 A11 原始字节一致，没有新增诊断。
- ARM64 候选 SHA256 `dcd19038416dca75684023c18eed79bcadaa980b5ea5efb3622096157f28d20b`，模型/sidecar/模板/锁与 01—05 冻结件一致。CPU-only 包164个文件，不含 PL 后端库；私有运行目录和资产目录此前均不存在。加载72个投影权重，GPU层0，2线程/context1024/物理T8。
- 固定 teacher-forced 输入分别按 T8 与 T1 执行：10行完整词表 logits 逐位一致；抽取层0/3/4/23的12组投影输入/输出通过既定门槛，混合状态逐位一致。每次响应前状态清空，位置回到-1。
- 一个冻结合成病例自然输入（46 prompt tokens）生成“胸口疼。”，3个输出token，EOS=true。仅功能样例，不代表医学审核或统计质量验收。
- v1 259次健康采样、254次进程观察：VmHWM=770636 KiB，采样RSS峰742476 KiB/PSS峰745190 KiB；最低 MemAvailable=2885608 KiB、CmaFree=216712 KiB，最高33.604°C。RSS/PSS、CMA、假设新增BO分开记账，不求和冒充物理峰值；瞬时峰值未覆盖。
- v1/v2 worker与manager均正常exit0。独立后验默认PL operating/GDM active，无ZOCL、计算设备FD/VMA、持锁或active lease；本轮硬件提交0，全局硬件计数null。原生子程序保留继承的PC标签，由实际ARM进程/板身份包装证明物理验证域BOARD，不改写原始输出。

## 失败、定位与边界

1. prepare_01 把历史日志当文本读取，换行标准化破坏摘要；改为原始字节解码后 preflight_02/prepare_02 通过。保留原失败与两次读回。
2. 额外 PC/x86 与 ARM 整图比较 **FAIL 保留**（logits最大差约0.85—1.36，固定整图门槛0.002+0.0002|ref|）。首层 MLP 前输入微差<=3.94e-6：扁平索引3745，ARM量化归一值1.49999046→1，PC为1.50001919→2。捕获ARM和PC各自输入，独立A04标量参考的8组输出均逐位相同，误差0。说明跨架构非MLP差异可经A8边界放大；没有放宽门槛或改数学。后续S1/S2必须使用本次同板基线；不能宣称跨ISA等价。本步既定验收为同板S1，不以跨ISA失败追认PL失败或忽略失败。
3. v1 单投影/单MLP容量余量通过；全模型140591104B假设BO扣除后CMA79416 KiB，不满足额外64MiB余量加32MiB底线（98304 KiB）。**首次完整范围容量判断仍FAIL**。仅对本任务三份归档fsync与posix_fadvise(DONTNEED)，保留内容、未drop_caches。独立v2窗口同binary/参数、teacher_T8、关闭诊断文件写入：81次健康采样，最低MemAvailable2953080/CMA432612 KiB，最高32.671°C。假设完整BO后CMA295316 KiB，原64MiB余量门槛通过。v2仅是受控资源测量，不冒充完整v1场景重跑。文件缓存影响已定位；未来须在归档缓存释放前提下新鲜检查，并实际逐BO核对地址/大小/group/总限额；不能据此保证完整PL分配成功。
4. 一次SSH认证连接关闭exit255，未收到执行输出；新收据执行唯一v2窗口。Windows审计因默认GBK失败；WSL audit_04 exit0，最终工具显式UTF-8。失败收据均留存。

算子阈值仍1e-4+1e-5|ref|，整图0.002+0.0002|ref|。来源：AUDIT.json、FAILURES.json、MINIMAL_CROSS_ISA_COUNTEREXAMPLE.json、SAME_INPUT_REFERENCE.json、两份readback tar及逐命令收据。最终历史契约/新版配置检查各exit0。

## 修改范围与后续

新增本地 `platform/qwen35/a12/step06_*.py`、本目录原始证据/报告与治理更新。板上只新增 `/opt/patient-qwen` 模型资产、`/var/lib/kv260-a12/step06-20261023-v1` CPU运行/结果和任务传输归档；临时CPU-only租约归档并释放双锁。没有重启、刷写、驱动/PL装卸、服务变更、强杀、全局缓存清理、公共契约改动、远程推送或子代理。固定2026.1/依赖和模型设置unknown保持。

本次到第06步结束。下次第07步应先重核身份/无设备用户/租约/资源，在独立窗口只做l00 gate，再做l00 gate/up/down的真实图消费与同板S1配对；不能直接跳到72投影。跨ISA整图限制、首轮容量失败及实际BO未测应进入后续报告。
'''
    (OUT/'REPORT.md').write_text(report,encoding='utf-8',newline='\n')
    p=ROOT/'docs/PROJECT_STATUS.json';old=json.loads(p.read_text(encoding='utf-8'))
    assert 'a12_step06_20261023' not in old
    new={'role':old['role'],'a12_step06_20261023':status}
    new.update({k:v for k,v in old.items() if k!='role'})
    new['stage']='A12';new['stage_status']='IN_PROGRESS_STEP06_BOARD_S1_PASS_WITH_LIMITATIONS_STEP07_NOT_STARTED'
    p.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    header='2026-10-23 A12 第06步：真实ARM64同板S1通过（有限范围）；T8/T1 logits及混合状态逐位一致、12组抽样投影通过、自然合成输入正常EOS。HWM770636 KiB，最高33.604°C；CPU-only两窗口正常退出，独立后验默认PL/GDM保持、无设备用户/ZOCL/锁/active lease。跨PC/ARM整图FAIL保留并定位到A8边界，同输入8组独立标量参考逐位一致；首次全模型资源附加余量FAIL保留，归档缓存定向释放后v2容量观察通过，实际PL BO/address/物理峰值仍未测。PL提交0、加速比null；07未开始。详见 `evidence/model_pl_A/20261023-step06-v1/REPORT.md`；以下旧阶段状态为历史快照。'
    for name in ('docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/status/A.md'):
        p=ROOT/name;lines=p.read_text(encoding='utf-8').splitlines(keepends=True)
        lines.insert(1,'\n'+header+'\n')
        p.write_text(''.join(lines),encoding='utf-8',newline='\n')
    p=ROOT/'docs/AI_ASSISTANCE.md';lines=p.read_text(encoding='utf-8').splitlines(keepends=True)
    lines.insert(1,'\n2026-10-23 使用 xilinx-suite/llama-cpp 技能，按用户第06步授权固定host-key/隐藏凭据连接板端，部署新CPU-only资产与独立窗口，保留失败并定位跨ISA量化边界及归档缓存资源问题；没有子代理、模型设置切换声明、凭据落盘、PL/驱动/服务切换、重启刷写或推送。实际设置unknown。'+header+'\n')
    p.write_text(''.join(lines),encoding='utf-8',newline='\n')
    p=ROOT/'docs/A12_STEP_PLAN_20261023.md';s=p.read_text(encoding='utf-8')
    start=s.index('### 06｜');end=s.index('### 07｜')
    section=s[start:end].replace('- [ ]','- [x]')
    section+='本轮实测：同板S1通过，容量判断仅在归档缓存定向释放后的v2条件下通过；首次完整范围余量FAIL及跨ISA整图FAIL保留。实际PL BO/地址/峰值未测，第07步开始前重新核对。报告 `evidence/model_pl_A/20261023-step06-v1/REPORT.md`。\n\n'
    s=s[:start]+section+s[end:]
    s=s.replace('06—11 未执行，BOARD NOT_TESTED','06 同板S1已验证；07—11 未执行，模型PL消费仍NOT_TESTED')
    s=s.replace('01—05 PC/交叉构建完成；06—11 未执行。','01—05 PC/交叉构建完成；06 同板S1通过（有限范围），07—11 未执行。')
    s+='\n## 8. 第06步执行更新\n\n'+header+'\n'
    p.write_text(s,encoding='utf-8',newline='\n')
    handoff=ROOT/'docs/handoffs/A_A12_STEP06_20261023.md'
    with handoff.open('x',encoding='utf-8',newline='\n') as f:f.write('# A12 第06步交接\n\n'+header+'\n\n下次仅在新鲜前置通过后进入07；沿用冻结模型/sidecar/输入与算子及整图阈值。不要用PC参考替代实际同板S1。板上新增资产与运行路径、独立后验、失败和容量前提均见报告。A11与01—05封存证据保持。\n')
    print(json.dumps(dict(status=status['status'],next_step=status['next_step'])))


if __name__=='__main__':main()
