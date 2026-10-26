"""Local evidence closeout for recovery diagnostics, never contacts the board."""
import datetime,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
E=ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1'
OUT=E/'recovery-authorized-20261025-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def j(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,obj):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
audit=j(OUT/'newboot-audit-01/stdout.txt');scene=j(OUT/'scene-03/stdout.txt')
network=json.loads(j(E/'logs/recovery_uart_network_nm_02.json')['stdout'])
assert network['Scene']['nm_unsaved']=='b true'
backup=j(OUT/'boot-backup-01/receipt.json');assert backup['status']=='PASS_PINNED_BOOT_BACKUP'
assert j(OUT/'scene-03/receipt.json')['exit_code']==0
assert scene['release_scan']['scan_complete'] and audit['scan']['scan_complete']
assert audit['active_inventory']['lease.json']['sha256']=='568d525f398a30b931f1767f4eec6ac19303814e781b1602d5756062f2a248e7'
assert len(audit['kernel_diagnostics'])==195
save(OUT/'UART_NETWORK_NM_02.json',network)
raw=audit['kernel_raw'].encode();assert hashlib.sha256(raw).hexdigest()==audit['kernel_sha256']
with (OUT/'CURRENT_KERNEL.raw.txt').open('xb') as f:f.write(raw)
save(OUT/'CURRENT_KERNEL_DIAGNOSTICS.json',dict(boot_id=audit['boot_id'],kernel=audit['kernel'],
    sha256=audit['kernel_sha256'],diagnostics=audit['kernel_diagnostics'],compute_gate='BLOCKED_UNREVIEWED_DIAGNOSTICS'))
progress=dict(status='INCOMPLETE_NETWORK_RESTORED_KERNEL_MISMATCH_STALE_LEASE_RETAINED',updated_beijing=now,
    task01_complete=False,current_machine_sha256=audit['machine_sha256'],current_boot_id=audit['boot_id'],
    current_kernel=audit['kernel'],required_compute_kernel='6.8.12-a10irq2',
    old_boot_id='86e4938b-0f65-4166-9237-c547b67e1451',old_manager_pid_absent=True,old_worker_pid_absent=True,
    old_manager_exit_code=None,old_worker_exit_code=None,old_exit_reason='UNKNOWN_BOOT_CHANGED_NOT_NORMAL_EXIT_PROOF',
    ssh=dict(exit_code=0,payload_sent=True,receipt='scene-03/receipt.json',host_key_pinned=True),
    network=dict(address='192.168.2.2/24',interface='eth0',connection_uuid='bf6e1c82-2a97-4698-a913-3993a03f3bd7',
        unsaved=True,persistent_configuration_written=False,host_network_changed=False,
        initial_raw_ip_add_later_disappeared=True,prior_attempts_preserved=True),
    lease=dict(retained=True,archived=False,sha256=audit['active_inventory']['lease.json']['sha256'],owner_is_prior_boot=True),
    process_scans=[dict(receipt='scene-03/stdout.txt',complete=True,inspected_processes=len(scene['release_scan']['inspected_processes'])),
                   dict(receipt='newboot-audit-01/stdout.txt',complete=True,inspected_processes=len(audit['scan']['inspected_processes']))],
    kernel_gate=dict(status='BLOCKED_UNREVIEWED_DIAGNOSTICS',count=195,raw_sha256=audit['kernel_sha256'],
        x509_warning_and_trace=True,baseline_waiver=False),
    default_overlay='applied',GDM='active',ZOCL='absent',normal_release='NOT_PROVEN',recovery_complete=False,
    boot_backup=backup,boot_plan='BOOT_PLAN.md',boot_plan_PC_checks=17,boot_contact_in_PC_checks=False,
    reboot_executed=False,power_or_reset_executed=False,flash_executed=False,signals_sent=0,
    cpu_close_deployed=False,new_window_prepared=False,new_PL_calls=0,TTFT_board_s=None,TTFT_le_10s='NOT_VERIFIED',
    source03_model_rerun=False,DeepSeek_used_this_recovery_step=False,
    routing_reason='Debugging, board recovery, kernel/evidence assessment and scoped boot planning remain with primary agent; short status writing done directly',
    actual_model_settings='unknown',prior_progress='PROGRESS.json')
save(OUT/'PROGRESS-02.json',progress)
report='''# TT10-01 恢复进展：网络恢复，内核阻断，未完成

用户已授权继续恢复，并接通J4数据USB；固定FTDI B/COM5串口与SSH均已核实为原板卡。网络原来没有IPv4；一次直接ip addr add成功后地址又消失，失败SSH/前后串口证据保留。随后按工程既有方案创建仅驻内存的NetworkManager连接，D-Bus确认Unsaved=true，192.168.2.2/24与固定主机密钥SSH复核成功。没有写永久网络、网关/DNS或改开发机网络。

当前boot d6d3b16f-f78c-4efa-acaa-14fc8b076fe8、内核6.8.0-1036-xilinx，已不是旧boot/6.8.12-a10irq2。旧manager167484/worker167575已不存在，如何退出及退出码未知；不得追记正常退出，也未执行旧PID恢复/强杀脚本。旧租约完整保留且SHA不变，未归档。完整FD/VMA只读扫描两次均通过（193/194进程），默认overlay applied、GDM active、ZOCL absent；这些观测不构成当前严格关闭门禁通过。

内核全文保存为CURRENT_KERNEL.raw.txt，SHA 9191287a4b763164d6010168548d6c8a5242ae1ea0f9903e7d84e17f9ec1e6f4。原严格诊断规则提取195行，包含X.509证书加载WARNING/调用栈，以及pinctrl、TPM、OP-TEE、overlay属性等诊断。195是匹配行数，不是195个独立故障。没有批准该基线、静默忽略告警或放宽释放门槛；因此旧租约继续保留、新窗口未准备。

原image.fit、boot.scr.uimg及已保存a10irq2候选均已只读备份到boot-backup-01，三件大小/SHA与板端及工程pin一致。既有候选启动流程PC 17项通过，不代表本轮已启动候选。下一步具体维护方案见BOOT_PLAN.md：专项确认一次正常重启并临时启动已有a10irq2，仅做只读复核；保留默认启动文件，不自动重试/复位/刷写。该新启动动作尚未获专项确认、未执行。

本次确实发生的板端改动仅为临时网络恢复及其独立恢复日志。无信号、重启、复位、刷写、模块/测试PL操作、模型运行或租约改写。CPU关闭通道26项PC通过仍为未部署；source-04的24项复核、14项回归、普通应用1对R0/hit、零后缀与A53构建通过均保留；未重跑source-03。此前字节码清理审批拒绝记录保留，未尝试绕过。

TT10-01未完成，新增PL调用0、实板TTFT=null、≤10秒NOT_VERIFIED，TT10-02未开始、A12第11步PENDING。原进度与全部失败证据保留；PROGRESS.json为较早网络阻断历史，本次以PROGRESS-02.json为准。本次调试/证据验收由主代理完成，未调用DeepSeek；既有DeepSeek排版回执不改。实际模型设置unknown。
'''
with (OUT/'PROGRESS-02.md').open('x',encoding='utf-8') as f:f.write(report)
shared=['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md']
before=OUT/'shared-before-02';before.mkdir(exist_ok=False)
snap={}
for name in shared:
    p=ROOT/name;raw=p.read_bytes();dest=before/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    snap[name]=dict(before_sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
status=j(ROOT/shared[0]);key='a12_ttft10_01_in_progress_20261025'
others={k:v for k,v in status.items() if k!=key};entry=status[key]
entry['status']=progress['status'];entry['updated_beijing']=now
entry['report']='evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/PROGRESS-02.md'
entry['next']=['Review/authorize the exact one-normal-reboot plus temporary irq2 recovery boot in BOOT_PLAN.md; no compute',
    'Fresh pinned-kernel identity/log/FD/VMA/default/lock checks; preserve original failure and unknown prior exit codes',
    'Only after strict release and stale-lease archival proof prepare an independent new board window']
board=entry['BOARD'];board['prior_isolated_window_record_20261025']=dict(board)
board.update(status='INCOMPLETE_BOOT_CHANGED_KERNEL_GATE_BLOCKED_STALE_LEASE_RETAINED',live_state_rechecked=True,
    historical_scene_only=False,current_boot_id=audit['boot_id'],current_kernel=audit['kernel'],manager_pid=None,cpu_worker_pid=None,
    old_manager_exit_code=None,old_worker_exit_code=None,lease_retained=True,
    normal_release_and_GDM_restore='GDM_ACTIVE_DEFAULT_APPLIED_BUT_STRICT_RELEASE_NOT_PROVEN',
    recovery_executed=False,network_recovery_executed=True,
    reason='Current boot kernel differs; unreviewed kernel diagnostics prevent strict release',
    outer_controller='Fresh pinned SSH scene-03 exit0; old owner absent, old lease retained')
entry['recovery_authorized_20261025'].update(status=progress['status'],report=entry['report'],
    summary='evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/PROGRESS-02.json',
    SSH_exit_code=0,payload_sent=True,board_live_state_rechecked=True,new_window_prepared=False,
    reboot_executed=False,stale_lease_archived=False)
assert others=={k:v for k,v in status.items() if k!=key}
p=ROOT/shared[0];assert sha(p)==snap[shared[0]]['before_sha256'];p.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
heading='## 2026-10-25 TT10-01串口/临时网络恢复，启动变化与内核告警阻断\n\n'
text='同板身份与固定SSH复核成功；仅驻内存的192.168.2.2/24连接Unsaved=true。当前boot d6d3b16f-f78c-4efa-acaa-14fc8b076fe8、6.8.0-1036-xilinx，旧PID已不在且退出码未知，旧租约原字节保留；未执行旧恢复/信号。两次完整FD/VMA扫描通过，默认overlay/GDM正常、ZOCL不在，但内核有X.509 WARNING/调用栈等195行严格诊断匹配，未批准为计算基线，严格释放尚未证明。三件启动原件只读备份大小/SHA一致；一次正常重启+已有irq2临时启动的具体维护方案已备，未获专项确认、未执行。本次无模型/测试PL/重启/刷写/租约改写，新窗口未准备。TT10-01未完成、新增PL=0、实板TTFT=null、≤10秒未验收；原PC通过、历史失败及A13条目保留。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/PROGRESS-02.md`，计划同级 `BOOT_PLAN.md`。本次调试与验收未委派DeepSeek，实际模型设置unknown。\n\n'
for name in shared[1:]:
    p=ROOT/name;assert sha(p)==snap[name]['before_sha256'];old=p.read_text(encoding='utf-8');p.write_text(heading+text+old,encoding='utf-8')
for name in shared:snap[name]['after_sha256']=sha(ROOT/name)
save(OUT/'SHARED_PROGRESS_RECEIPT-02.json',dict(updated_beijing=now,files=snap,other_project_status_entries_unchanged=True))
handoff=ROOT/'docs/handoffs/A12_TT10_01_UART_RECOVERY_20261025.md'
with handoff.open('x',encoding='utf-8') as f:f.write(report+'\n接续保留原恢复授权；专项正常重启/候选启动须先确认BOOT_PLAN.md范围。不要自动复用旧boot/PID或把无板通过转记BOARD。\n')
print(json.dumps(dict(status=progress['status'],report=str(OUT/'PROGRESS-02.md'),shared_files=len(shared)),ensure_ascii=False))
