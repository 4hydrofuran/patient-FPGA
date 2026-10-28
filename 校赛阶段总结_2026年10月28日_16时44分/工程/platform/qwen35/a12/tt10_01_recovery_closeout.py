"""Close out recovery/preparation facts locally. No compute success promotion."""
import datetime,hashlib,json
from pathlib import Path
from tt10_01_common import ROOT,OUT,sha,save
def j(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def text(p,s):
    with Path(p).open('x',encoding='utf-8') as f:f.write(s)
def main():
    rec=OUT/'recovery-authorized-20261025-v1';win=OUT/'window-20261025-v2'
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    scene=j(rec/'independent-postcheck-01/stdout.txt');prepared=j(win/'PREPARED.json')
    assert j(rec/'independent-postcheck-01/receipt.json')['exit_code']==0
    assert scene['active_lease'] is None and scene['release_scan']['scan_complete']
    assert not scene['release_scan']['device_holders'] and not scene['release_scan']['device_mappings']
    assert all(not v['matching_rows'] for v in scene['canonical_locks'].values())
    assert scene['recovery_archive']['sha256']=='568d525f398a30b931f1767f4eec6ac19303814e781b1602d5756062f2a248e7'
    boot=j(rec/'irq2-boot-once-02.json');assert boot['closed'] and boot['boot_commands_sent']==1 and boot['error'] is None
    assert scene['boot_maintenance']['reboot-command.json']['exit_code']==0
    for name in ('independent_window_import_01','independent_window_plan_only_01','recovery_stale_lease_pc_01','recovery_uart_delivery_pc_01'):
        assert j(OUT/'logs'/(name+'.json'))['exit_code']==0
    bundle=win/'bundle-v3';manifest=j(bundle/'manifest.json')
    for row in manifest['files']:
        p=bundle/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    assert not list(bundle.rglob('*.pyc'))
    original=OUT/'candidate/bundle-v2';pm=j(original/'manifest.json')
    assert all(sha(original/r['path'])==r['sha256'] for r in pm['files'])
    summary=dict(status='RECOVERY_COMPLETED_PRIOR_FAILURE_PRESERVED_NEW_WINDOW_PC_PREPARED',updated_beijing=now,
        task01_complete=False,current_machine_sha256=scene['machine_sha256'],current_boot_id=scene['boot_id'],current_kernel=scene['kernel'],
        normal_reboots_executed=1,candidate_boot_commands=1,hard_resets=0,flash_operations=0,default_boot_files_changed=False,
        old_window=dict(status='FAILED_CPU_RESERVE_GATE_PRESERVED',old_boot='86e4938b-0f65-4166-9237-c547b67e1451',
            manager_exit_code=None,worker_exit_code=None,normal_owner_exit=False,lease_archived=True,
            archive=scene['recovery_archive']['path'],lease_sha256=scene['recovery_archive']['sha256']),
        recovery=dict(status='PASS_SCOPED_RECOVERY_POSTCHECK_ONLY',active_lease=False,canonical_locks_unheld=True,
            FD_VMA_scan_complete=True,inspected_processes=len(scene['release_scan']['inspected_processes']),
            GDM='active',default_overlay='applied',ZOCL='absent',independent_postcheck='independent-postcheck-01/stdout.txt',
            kernel_recovery_review='IRQ2_KERNEL_RECOVERY_REVIEW-02.json',kernel_raw_sha256=scene['kernel_log']['sha256'],
            startup_limitations_still_open=True,compute_baseline_review_included=False),
        PC=dict(source04_scoped_checks=24,harness_checks=14,ordinary_R0_hit_pairs=1,zero_suffix_pairs=1,
            source04_A53_cross_build='PASS_NOT_EXECUTED_ON_BOARD',CPU_close_checks=26,UART_delivery_guards=9,
            stale_owner_archive_guards=9,isolated_package_import='PASS_NO_MODEL_RUN',default_driver_plan_only='PASS'),
        new_window=prepared,new_PL_calls=0,TTFT_board_s=None,TTFT_le_10s='NOT_VERIFIED',source03_model_rerun=False,
        DeepSeek_used_this_recovery_step=False,actual_model_settings='unknown',
        preserved_failures=['normal-reboot-once-01: pending local auth cancelled; payload not sent; no reboot',
            'irq2-boot-once-01: passive deadline, no countdown/bytes/boot',
            'recovery_uart_postboot_01: USB disconnect during read-only capture',
            'stale-lease-01: kernel hash refusal before archive; CR conversion and local UTF-8 decode issues diagnosed',
            'prepare_independent_window_01: observed sysfs status retained newline; refusal before directory creation'],
        original_manifested_files_still_equal=len(pm['files']),prior_extra_bytecode_cleanup='REJECTED_NO_DELETION_NO_RETRY')
    save(rec/'SUMMARY-RECOVERY.json',summary)
    save(rec/'BOOT_EXECUTION.json',dict(authorization='BOOT_AUTHORIZATION.json',normal_reboots=1,
        normal_reboot_command_exit_code=0,SSH_disconnect_exit_code=j(rec/'normal-reboot-once-02/receipt.json')['exit_code'],
        SSH_receipt='normal-reboot-once-02/receipt.json',UART_receipt='irq2-boot-once-02.json',candidate_bootm_commands=1,
        note='UART cold-boot controller reboot_commands_sent=0 counts only its own commands; the single normal reboot was sent by the separate guarded SSH helper',
        new_boot=scene['boot_id'],kernel=scene['kernel'],default_boot_files_modified=False,PL_compute_calls=0))
    report='''# TT10-01：恢复完成，独立窗口已在电脑端准备，阶段未完成

## 本轮实际结果

J4数据线重连后固定FTDI B/COM5复核通过；首次postboot只读采集因USB端口断开失败，记录保留。一次正常重启及一次临时bootm已获专项授权并完成，当前boot为1d0499ab-f1f9-438c-969a-3e701a0d806f、内核6.8.12-a10irq2。同板machine-id、原启动文件、候选FIT、已安装ZOCL文件、XRT库哈希均匹配。三件启动文件完整本机备份保留。没有saveenv、刷写或改默认启动文件，没有第二次重启/硬复位。

SSH在正常重启时断开，原Windows返回码4294967295保留；板端reboot-command.json明确exit0，串口核对U-Boot/三组件哈希/载板配置后仅发出一次bootm并见登录。首次认证等待已取消且payload_sent=false，首次被动捕获超时没有发送任何启动字节，都不占用额外重启。

当前内核启动诊断与原TT10-01已审查基线对照：原250行匹配，本次186行匹配；除同一X.509栈CPU编号和一个x22寄存器值外，本次每项诊断及次数均已存在于旧基线。此前PL动作产生的诊断在本次新启动中不存在。这些是仍OPEN的已知限制，不是修复或计算验收。本次仅将精确原始字节SHA e6c899a5780c7c6c6549ff11fa8940654665ba699e4c5e85c088fbb5f401069e审查为恢复基线；后续新诊断继续锁存拒绝。计算阶段仍需独立新鲜基线与资源审查。

## 旧失败与归档证据

旧boot已在本轮首次接通串口前变化，旧manager167484/worker167575不在；退出方式/退出码均未知，原CPU余量拒绝不转记正常退出或计算PASS。本轮未向板端进程发送信号。旧租约在新boot持有协调锁及双规范锁、完整FD/VMA扫描、内核连续性、默认overlay/GDM、原件哈希复核后，以renameat2(RENAME_NOREPLACE)原样移入：

`/var/lock/kv260-a1/history/a12-tt10-01-20261024-v1-priorboot-abnormal-20261025-v1/lease.json`

租约SHA仍为568d525f398a30b931f1767f4eec6ac19303814e781b1602d5756062f2a248e7。归档后的独立SSH只读后检exit0：活动租约为空、两把规范锁无持有者、完整扫描无加速器FD/VMA持有者、默认overlay applied、GDM active、ZOCL absent。范围仅为恢复/归档通过，TT10-01计算BOARD仍未验收。

首次归档前的严格哈希检查拒绝已保留：UART脚本text=True转换了41个CR，随后一次本地JSON读取未指定UTF-8又误解码了版权符号。已改为二进制采集+base64/长度/SHA、显式UTF-8，修正后UART与SSH的58363原始字节完全相同；不对日志做归一化来绕过严格比较。早期误标raw的转换产物、失败、纠正说明全部保留（UART_KERNEL_NEWLINE_FAILURE.json）；新的精确审查以IRQ2_KERNEL_RECOVERY_REVIEW-02.json为准。

## 独立板测窗口准备

电脑端新包为同证据根window-20261025-v2/bundle-v3；新window_id=a12-tt10-01-20261025-v2，拟用全新远端目录/租约，未部署、未执行。包含source-04 A53程序及最终CPU关闭manager-source-03；关闭mixin放在-I模式明确加入的platform/qwen35/a12导入目录。保持旧6项请求、70token前缀、5000硬上限/4752最坏调用预算、原内存/CMA阈值、公共数学/ABI/硬件不变。新驱动默认PLAN_ONLY，执行需要准确窗口参数及另行计算授权；现有启动维护授权不包含计算。

包内Python编译、Linux -B -I真实导入/继承来源、驱动默认PLAN_ONLY、全部manifest字节/SHA通过。原父包165个manifest文件仍相同；只复制清单文件，没有复制或删除历史额外字节码。原清理审批拒绝记录仍保留，未绕过。准备过程第一次因sysfs状态末尾换行拒绝，发生在新目录创建前，原失败保存；修正为对状态枚举去除行尾后严格比对。

## 通过项、待办与边界

原source-04 24项严格复核、14项脚本回归、普通应用1对R0/hit、零后缀、A53交叉构建，以及CPU关闭26项PC检查继续有效；未重跑source-03。新增UART发送时限9项、跨启动归档9项PC检查和新包隔离导入/PLAN_ONLY检查通过。恢复已完成，启动文件/平台默认状态保留。DeepSeek未参与本轮调试/板端/验收，短状态记录由主代理直接完成；历史排版调用回执保留，实际模型设置unknown。

下一步是单独审查新包的即时计算基线、资源余量、全新命名空间和双锁/唯一租约，再由用户明确授权这一独立计算窗口。需要在板上实际核对关闭通道、完整数值、普通应用R0/hit与真实少算/TTFT。仍不得将PC、交叉构建或恢复后检当作计算BOARD通过；源04关闭通道未在板端运行。V07/V08质量拒绝、教师审核PENDING、原历史失败保留。

TT10-01未完成；本轮新增PL调用0，实板TTFT=null，≤10秒NOT_VERIFIED，TT10-02未开始，A12第11步PENDING，A13条目保留。PROGRESS-02与BOOT_PLAN的未授权/未归档措辞为较早历史，已分别由BOOT_AUTHORIZATION、BOOT_EXECUTION与本报告覆盖。
'''
    text(rec/'REPORT-RECOVERY.md',report)
    text(win/'PLAN.md','''# 独立TT10-01窗口：仅准备，未部署或执行

窗口a12-tt10-01-20261025-v2，拟用/var/lib/kv260-a12/tt10-01-20261025-v2。PREPARED.json包含包/驱动/原生程序/管理器哈希。上一失败窗口已归档且独立后检通过；不复用其运行目录或租约。

包为source-04 A53 + manager-source-03关闭通道。原6个有界请求及顺序不变：diag_exact、warm_prefix、diag_full_R0、diag_hit、app_R0、app_hit；分别CPU/真实PL各执行一轮。前缀70token、每后台普通应用1对；硬上限5000、最坏4752 PL调用、最多72权重加载、1800秒会话。保留全数值原件、严格哈希、必要同步和未知DMA隔离，不作统计或10秒达标推断。

执行前必须重新核对当前boot/内核、内核完整基线、MemAvailable/CmaFree实时门槛、温度、磁盘、无持有者、全新远端目录、双锁/唯一租约，且取得该独立计算窗口的明确授权。历史基线审查仅覆盖恢复，不自动给计算授权。

board_driver_plan.py默认仅输出PLAN_ONLY，无板端调用；当前未分发。准确执行参数由主代理在获批后绑定到审查过的传输入口，不能把现有临时启动授权用作计算授权。任何失败仍保持原失败；CPU合作关闭通过也不转记计算PASS。失败退出后如外层不产生独立后检，需另用只读后检证明释放，不能因退出1自动重跑。

尚待BOARD验证：CPU关闭通道、完整R0/命中数值及原始状态、真实少算/完成数、普通应用首token及EOS、正常平台恢复与独立后检。当前BOARD=NOT_TESTED、TTFT=null、TT10-01未完成。
''')
    shared=['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md']
    folder=rec/'shared-before-final';folder.mkdir()
    snapshots={}
    for name in shared:
        raw=(ROOT/name).read_bytes();p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        snapshots[name]=dict(before_sha256=hashlib.sha256(raw).hexdigest())
    status=j(ROOT/shared[0]);key='a12_ttft10_01_in_progress_20261025';others={k:v for k,v in status.items() if k!=key}
    s=status[key];s.update(status='INCOMPLETE_RECOVERY_DONE_INDEPENDENT_WINDOW_PC_PREPARED',updated_beijing=now,
        report='evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/REPORT-RECOVERY.md')
    s['BOARD'].update(status='TT10_01_COMPUTE_NOT_ACCEPTED_RECOVERY_DONE',current_boot_id=scene['boot_id'],current_kernel=scene['kernel'],
        reason='Prior CPU reserve failure preserved; new independent compute window prepared but not executed',
        lease_retained=False,lease_archived=True,manager_pid=None,cpu_worker_pid=None,old_manager_exit_code=None,old_worker_exit_code=None,
        normal_release_and_GDM_restore='CURRENT_DEFAULT_GDM_AND_LOCK_RELEASE_PROVEN_AFTER_PRIORBOOT_ARCHIVE_OLD_EXIT_UNKNOWN',
        recovery_executed=True,live_state_rechecked=True,outer_controller='Fresh independent postcheck exit0; no active lease or lock owner',
        recovery_authorization='RECOVERY_AND_ONE_NORMAL_REBOOT_USED_NO_NEW_COMPUTE_AUTHORIZATION',actual_PL_calls=0,TTFT_app_s=None)
    s['recovery_authorized_20261025'].update(status=summary['status'],report=s['report'],
        summary='evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/SUMMARY-RECOVERY.json',
        SSH_exit_code=0,payload_sent=True,board_live_state_rechecked=True,reboot_executed=True,stale_lease_archived=True,new_window_prepared=True)
    s['independent_window_pc_prepared']=prepared
    s['next']=['Fresh independent compute-specific review and explicit scoped authorization for 20261025-v2',
        'Actual source04/CPU-close BOARD numerical, R0-hit work/timing and release verification; no prior failure replay',
        'TT10-01 stays incomplete, new PL calls0 and TTFT null until actual evidence']
    assert others=={k:v for k,v in status.items() if k!=key}
    assert sha(ROOT/shared[0])==snapshots[shared[0]]['before_sha256']
    (ROOT/shared[0]).write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    paragraph='''## 2026-10-25 TT10-01恢复完成，独立窗口PC包准备完成，计算BOARD未验收

专项一次正常重启+临时irq2启动完成，当前boot1d0499ab-f1f9-438c-969a-3e701a0d806f/6.8.12-a10irq2。旧失败租约原样归档，旧进程退出码仍null；独立后检证实活动租约空、规范双锁无主、完整FD/VMA扫描通过、默认overlay/GDM正常、ZOCL不在。启动告警对照旧基线后仅按精确原始哈希审查为恢复基线，已知限制仍OPEN、后续新增诊断不豁免。UART文本模式41个CR转换及一次本地UTF-8误读导致的首次归档拒绝保留；已用二进制base64/长度/SHA与SSH原始58363字节完全互认，严格门禁未放宽。

新window-20261025-v2/bundle-v3包含source-04 A53和最终CPU关闭通道，PC隔离导入/清单哈希/默认PLAN_ONLY通过；未部署、未执行，需新鲜计算审查及明确独立计算授权。原24/14项source-04、普通R0/hit/零后缀、A53和26项CPU关闭PC通过保留；source-03未重跑。TT10-01未完成、新增PL=0、实板TTFT=null、≤10秒未验收，TT10-02未开始、A12第11步PENDING、A13保留。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/REPORT-RECOVERY.md`，新窗口 `evidence/model_pl_A/20261024-ttft10-01-v1/window-20261025-v2/PLAN.md`。本次调试/恢复/验收未委派DeepSeek，实际模型设置unknown。

'''
    for name in shared[1:]:
        p=ROOT/name;assert sha(p)==snapshots[name]['before_sha256'];old=p.read_text(encoding='utf-8');p.write_text(paragraph+old,encoding='utf-8')
    for name in shared:snapshots[name]['after_sha256']=sha(ROOT/name)
    save(rec/'SHARED_CLOSEOUT_RECEIPT.json',dict(files=snapshots,other_project_status_entries_unchanged=True))
    text(ROOT/'docs/handoffs/A12_TT10_01_RECOVERY_AND_WINDOW_PREP_20261025.md',report+'\n接续从新窗口PLAN.md与最新PROJECT_STATUS开始，不复用旧boot/PID/租约，不重发已经使用的一次启动维护。\n')
    print(json.dumps(dict(status=summary['status'],report=str(rec/'REPORT-RECOVERY.md'),window=str(win/'PLAN.md')),ensure_ascii=False))
if __name__=='__main__':main()
