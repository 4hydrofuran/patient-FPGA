"""Publish task07 completion with unchanged historical failures and no task08 claim."""
import datetime
import json
from common import ROOT,sha,save
from step07_mlp_prepare import OUT

def j(path):return json.loads(path.read_text(encoding='utf-8'))

def main():
    a=j(OUT/'AUDIT.json');f=j(OUT/'FINAL_CHECK.json')
    assert a['status']=='PASS_BOARD_L00_MLP_REAL_CONSUMPTION_AND_NORMAL_CLOSEOUT'
    assert f['all_logits_projections_nodes_and_state_bit_exact']
    for n in ('contracts_01','config_01','package_02','pc_graph_01','source_review_01','upload_01','download_01','audit_01','final_check_01'):
        assert j(OUT/(n+'.json'))['exit_code']==0,n
    for n in ('preflight_01','stage_01','identity_rejection_01','launch_01','readback_01','status_01','delayed_01'):
        assert j(OUT/n/'receipt.json')['exit_code']==0,n
    events=a['lifecycle']['finalization_events'];observations=[e for e in events if e['event']=='FULL_PROCESS_OBSERVATION']
    status=dict(status='PASS_A12_STEP07_SINGLE_PROJECTION_AND_SINGLE_MLP_BOARD',
       updated_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
       scope='l0',actual_PL_calls=9,jobs=[1,2,3,73,74,75,145,146,147],physical_T=[8,8,8,1,1,1,1,1,1],
       weight_loads=3,explicit_BO_count=10,explicit_BO_bytes=6062080,
       numeric='BIT_EXACT_SAME_BOARD_S1_S2',logit_rows=10,projection_records=36,downstream_nodes=72,
       hybrid_state_bytes=a['hybrid_state']['bytes'],resources=a['resource'],
       manager_pid=31361,wrapper_pid=31354,manager_exit_code=0,worker_exit_codes=[0,0],
       current_board='DEFAULT_PL_GDM_RESTORED_NO_ZOCL_DEVICE_USERS_ACTIVE_LEASE_OR_LOCKS',
       forced_signals=0,finalization_scan_attempts=len(observations),
       first_finalization_scan='INCOMPLETE_TRANSIENT_PROCESS_CHURN_SAVED',final_scan='COMPLETE_PASS',
       hardware_global_count=None,board_speedup=None,physical_peak_bytes=None,
       task06_failures='PRESERVED_DEFERRED_BY_USER',old_single_manager_exit=-9,
       task07='COMPLETE_WITH_DOCUMENTED_DOMAIN_LIMITS',task08='NOT_STARTED',full_model_PL='NOT_TESTED',
       model_settings='unknown',subagents=0,contract_changed=False,model_math_changed=False,B_core_changed=False,
       default_FPGA_enabled=False,committed=False,pushed=False,
       report='evidence/model_pl_A/20261024-step07-mlp-v1/REPORT.md')
    save(OUT/'SUMMARY.json',status)
    save(OUT/'FAILURES.json',[
       dict(id='package_01',domain='LOCAL_PC',exit_code=1,problem='Windows default GBK could not decode UTF-8 request file',
            resolution='Explicit UTF-8; failed draft retained in failed-package-01; package_02 passed before upload; no hardware action'),
       dict(id='finalization_scan_01',domain='BOARD_READONLY_OBSERVATION',status='INCOMPLETE_PRESERVED_RECHECK_PASSED',
            problem=observations[0]['scan']['scan_issues'],resolution='Strict v2 recognized only transient process/FD churn; second full observation complete; manager normal exit0 without signals',
            raw_record='readback-v1/run-v1/s2/finalization-events.jsonl'),
       dict(id='wrong_contract_expected_rejection',domain='BOARD_NEGATIVE_TEST',actual_worker_exit=2,status='EXPECTED_PASS_REJECTION',accelerator_submissions=0),
       dict(id='step06_historical',domain='HISTORICAL_BOARD_PC',status='FAIL_PRESERVED_DEFERRED_BY_USER',
            items=a['deferred_failures'],new_reassessment='NOT_TESTED'),
       dict(id='single_projection_old_closeout',domain='HISTORICAL_BOARD',status='OLD_FAIL_AND_ABNORMAL_EXIT_PRESERVED_SEPARATE_RECOVERY_COMPLETE',manager_exit=-9)])
    summary='2026-10-24 A12第07步完成：l00 gate/up/down共9次真实PL调用，T8/1/1，3份权重仅加载一次、10个BO共6062080B复用。实际Y分别被GLU/残差ADD消费；同板S1/S2的10行logits、36份投影输入输出、72诊断节点和混合状态逐位一致。两worker及manager正常exit0；v2首轮扫描短暂进程变化保留，第二次完整扫描通过后自行归档租约和释放双锁，未发强制信号。独立及延时复核默认PL/GDM恢复、无ZOCL/设备用户/active lease/相关进程。第06步两项FAIL及旧单投影收口FAIL/-9保留，第08步未启动，默认FPGA未开启、加速比null。报告 `evidence/model_pl_A/20261024-step07-mlp-v1/REPORT.md`。下方内容为历史快照。'
    text=f'''# A12 第07步：单投影与单 MLP 已跑通

**PASS_A12_STEP07_SINGLE_PROJECTION_AND_SINGLE_MLP_BOARD**。既有单投影证据保留，本轮扩大到第一层 gate/up/down，真实模型消费 PL 返回结果，数值与同板 CPU 逐位一致，管理器正常退出并完整恢复。第08步未启动。

## 本轮实测

- 同一锁定模型/sidecar、ARM程序、2线程、context1024、全72投影CPU同数学图、物理T8；只将第一层3个投影改为真实PL。固定tokens1..9，teacher10/11，单请求，T8 prefill、T1尾块、T1 decode；其余层同板CPU计算。
- 共9次真实PL调用，job1/2/3、73/74/75、145/146/147；每次ERT=4、64字节raw meta、job/build/status/done均独立核验。host完成次数9，硬件全局计数接口不存在，保持null。
- gate/up的Y被ffn_swiglu-0(GLU)消费；down的Y被l_out-0(ADD)消费。每次关联真实输入、输出SHA和消费者执行；不是只看生成文本相似。
- 10行全词表logits、36份投影输入/输出、72个首层诊断节点、{a['hybrid_state']['bytes']}字节混合状态均逐位相同；新S1与06的S1也一致。算子门槛1e-4+1e-5*abs(ref)，图门槛.002+.0002*abs(ref)，未改动。
- 权重加载3次，每份一次；IO和权重地址全程稳定。10个显式BO，共6062080B，group3、8192分配对齐、低2GiB且不重叠。物理总峰值、硬件全局计数和板端加速比仍null。
- 128份健康采样：MemAvailable最低{a['resource']['min_MemAvailable_kib']}KiB，CmaFree最低{a['resource']['min_CmaFree_kib']}KiB，最高温{a['resource']['max_temperature_mC']/1000:.3f}°C；S1/S2 RSS HWM分别{a['resource']['S1_RSS_HWM_kib']}/{a['resource']['S2_RSS_HWM_kib']}KiB。资源采样不冒充总物理峰值或性能实验。

## 收口与拒绝验证

管理器31361与包装器31354、两worker均已退出；manager和worker实际退出码均0。本轮明确引用固定摘要的Window v2。首轮完整观察时两个进程/FD消失，原始不完整结果保存在finalization-events.jsonl；严格识别为可重查变化后，第二次完整FD/VMA扫描通过，随后原子归档租约、关闭自己的锁FD。没有强杀、恢复票据、重启或刷写。

独立读回及延时复核：同boot/irq2内核，默认PL operating、GDM active、ZOCL无、设备FD/VMA无、active lease无、规范双锁无持有者，四个已知进程均不存在；归档租约摘要与本窗口预期字节相符。原单投影管理器-9仍只属于旧窗口，不追认为正常退出。

ARM实际错契约测试返回2并明确身份错误，发生在router_open许可/后端dlopen之前，硬件提交0；未注入DMA挂死。PC真模型l0正确性及丢弃Y反例通过；已完成的真实down输出在本机改一位后被SHA关联验证拒绝，属于PC读取BOARD结果的验证域，没有新增硬件调用。危险超时/复位仅沿用PC域，不宣称板测。

## 失败、产物与边界

首次本地打包因Windows GBK读取UTF-8失败，已显式指定编码，失败草稿与退出码保留；修复在上传前完成。本轮短暂不完整扫描也保留。详见FAILURES.json。

第06步跨ISA整图FAIL、首次完整范围容量FAIL依用户要求保留，未统一复验；本轮通过同板配对及单MLP预算，不把两个历史FAIL改成PASS。完整24层PL、自然连续生成、长稳、取消故障板测、速度收益及默认模块切换不在此次验收范围。

本地原始结果：readback-v1/run-v1，数值审计AUDIT.json，最终独立复核FINAL_CHECK.json；固定输入、私有运行配置、ERT/meta、每次输出和健康/生命周期日志均保留。新板包根 `/var/lib/kv260-a12/step07-mlp-20261024-v1`，manifest SHA `{j(OUT/'UPLOAD.json')['manifest_sha256']}`；ARM程序SHA `18d3d929cafdaa5043be5e4febf6150a938f12be5a1ea2da56d36be893a6c7d4`。旧计算包和封存证据不覆盖。

实际命令/退出码见contracts_01/config_01、package_01/02、pc_graph_01、source_review_01、upload_01、download_01、audit_01、final_check_01及各SSH目录receipt/reservation。凭据仅隐藏交互，不落盘；无子代理、依赖升级、源码推送或默认FPGA启用。模型/推理强度实际设置无法读取，记unknown。
'''
    (OUT/'REPORT.md').write_text(text,encoding='utf-8',newline='\n')
    status_path=ROOT/'docs/PROJECT_STATUS.json';current=j(status_path)
    current={'role':current['role'],'a12_step07_mlp_20261024':status,**{k:v for k,v in current.items() if k!='role'}}
    current['stage']='A12';current['stage_status']='IN_PROGRESS_STEP07_PASS_SINGLE_MLP_STEP08_NOT_STARTED'
    status_path.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for name in ('docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md'):
        p=ROOT/name;s=p.read_text(encoding='utf-8');lines=s.splitlines(keepends=True)
        s=lines[0]+'\n'+summary+'\n\n'+''.join(lines[1:])
        if name.endswith('A12_STEP_PLAN_20261023.md'):
            start=s.index('### 07｜');end=s.index('### 08｜',start)
            section=s[start:end].replace('- [ ]','- [x]')
            section=section.replace('扩大到 l00 gate/up/down（三个投影本轮未执行）。','l00 gate/up/down三投影已完成本轮9次BOARD调用及数值/消费核验。')
            section=section.replace('三投影MLP的新范围计算/正常生命周期尚未执行，本轮不扩大。','三投影MLP新窗口正常生命周期已通过，manager/worker exit0；独立及延时复核释放/恢复通过。')
            s=s[:start]+section+s[end:]
        p.write_text(s,encoding='utf-8',newline='\n')
    handoff=ROOT/'docs/handoffs/A_A12_STEP07_MLP_COMPLETE_20261024.md'
    with handoff.open('x',encoding='utf-8',newline='\n') as out:
        out.write('# A12 第07步单MLP完成交接\n\n'+summary+'\n\n下一步为08，但本轮未执行；任务06两项历史FAIL仍待后续统一评估。后续新窗口须再次新鲜核对板端、预算、内核/设备及锁租约，不能复用此次许可。新包使用Window v2，严格完整扫描重查已实际BOARD验证，首轮失败快照保存；旧单投影-9事实保持。详细原始证据和限制以报告为准。\n')
    print(json.dumps(dict(status=status['status'],report=status['report'])))

if __name__=='__main__':main()
