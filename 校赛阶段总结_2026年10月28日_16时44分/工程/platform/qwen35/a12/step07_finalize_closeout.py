"""Publish recovery-only completion while preserving all earlier experiment facts."""
import datetime
import json
from common import ROOT,save

OUT=ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1'


def main():
    a=json.loads((OUT/'AUDIT.json').read_text(encoding='utf-8'))
    assert a['status']=='PASS_FINALIZE_ONLY_OLD_ABNORMAL_EXIT_PRESERVED'
    assert not a['active_lease'] and not a['canonical_locks_held'] and a['new_computation']==0
    for name in ('policy_pc_01','window_v2_pc_02','audit_02'):
        assert json.loads((OUT/(name+'.json')).read_text(encoding='utf-8'))['exit_code']==0
    status=dict(a,updated_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        scope='RECOVERY_FINALIZATION_ONLY_NO_SCOPE_GROWTH',A12='IN_PROGRESS_SINGLE_PROJECTION_ONLY',
        original_step07_finalization='FAIL_PRESERVED_SEPARATE_RECOVERY_COMPLETE',single_projection='PASS_PREVIOUS_SEALED_BOARD_EVIDENCE',
        three_projection_MLP='NOT_TESTED',step08='NOT_STARTED',model_settings='unknown',subagents=0,
        model_math_changed=False,contract_changed=False,B_core_changed=False,default_FPGA_enabled=False,
        future_component_BOARD='NOT_TESTED',committed=False,pushed=False,
        report='evidence/model_pl_A/20261024-step07-finalize-v1/REPORT.md')
    save(OUT/'SUMMARY.json',status)
    save(OUT/'FAILURES.json',[
      dict(id='step07_original_finalization',domain='HISTORICAL_BOARD',status='FAIL_PRESERVED_RECOVERED_SEPARATELY',
           problem='One incomplete final process observation; no saved failed snapshot or live recovery IPC',
           resolution='Exact no-device waiting manager retired via one identity-bound pidfd SIGKILL after fresh full gates; original -9 retained. Canonical locks reacquired by independent finalizer, unchanged lease archived, finalizer exit0 and two independent readbacks clear. Exact cause of original incomplete scan remains unproven'),
      dict(id='audit_01',domain='LOCAL_OFFLINE_DERIVATION',exit_code=1,
           problem='Future Window v2 hand-edit applied retry-file logging change to base method instead of override, differed from generator',
           resolution='Unexecuted local draft and first test receipt retained; regenerated canonical source from one recipe; 7 final PC methods and exact-source hash verification pass. This local component was not used in BOARD retirement'),
      dict(id='step06_deferred',domain='HISTORICAL',status='UNCHANGED_DEFERRED_BY_USER',
           problems=['PC/ARM whole graph FAIL','First full-range conservative capacity FAIL'],new_validation='NOT_TESTED')])
    text='''# A12 第07步专项收口：已解决（2026-10-24）

**PASS_FINALIZE_ONLY_OLD_ABNORMAL_EXIT_PRESERVED**。旧等待管理器及其包装进程已结束，规范双锁释放，旧隔离租约按原字节归档。独立读回和延时复核均通过。此次只处理收口，新增模型/PL计算、PL/驱动装卸、服务启停、重启、刷写均为0；第07步三个MLP投影及第08步未执行。

## 实际处理

1. 固定host key/网卡地址SSH，隐藏认证，先旧契约保护检查与新版配置检查。新鲜核对同一machine-id摘要、boot `8422f92f-d01f-4849-ad19-6e66b640a9ad`、irq2内核和XRT/启动/默认PL文件摘要。
2. 重新确认27132/startticks2110722确为原等待管理器：一个睡眠线程、无子进程、无XRT映射、无设备FD，仅六个已知日志/锁描述符；两计算worker原正常exit0、真实结果/退出记录与已封存摘要一致。全进程FD/VMA扫描完整，ZOCL缺席、默认PL operating/GDM active、无新增内核诊断，双锁和租约仍属于旧窗口。
3. 该旧版本屏蔽HUP/INT/QUIT/TERM，保留循环无受控入口。依据用户本次优先解决该收口的授权，先通过本机真实等待子进程/文件锁测试，再执行**一次pidfd定向SIGKILL**，只结束此已证实不持设备的等待管理器。信号前再次实读全部门槛，PID/startticks/租约/清单固定；没有进程组信号、调试器注入、强制卸载、OFD偷锁或重复信号。
4. 旧wrapper27125正常完成wait并记录旧manager **exit=-9**。新finalizer29481独立获取规范双锁，复核设备/平台后，把旧active目录原子改名到`/var/lock/kv260-a1/history/a12-single-gate-20261023-v1-finalized-20261024-v1`。租约摘要仍`134e60a86225a80555428f7ff68e28e4c82db26916123db65e11628a9f92c411`，内容没有改写。新finalizer正常exit0；旧原始ISOLATED/失败记录不覆盖。
5. 独立读回：无设备FD/VMA/ZOCL/active lease/规范双锁或收口协调锁；默认PL/GDM保持正常。延时复核27132、27125、29481、29471全部不存在，内核无新增诊断。板端收尾记录跨度约2.315秒，不含SSH认证、PC测试、传输和报告时间；不是推理性能。

**旧manager的-9不会被追认为正常退出，首次收口FAIL也不会被擦除。** 当前资源清场通过，单投影原数值/消费通过保留；三投影MLP/完整范围仍未测，不能据此签全部第07步或A12通过。全局硬件计数仍null。快照不代表持续监控。

## 防止再次出现同类陷阱

新增独立`window_closeout_v2.py`，保留旧`window.py`、已部署单投影包及全部封存证据。新组件保存每次失败扫描，只有已识别的进程/FD表短暂变化才有界重查（最多4次）；未知异常、设备占用、boot或内核异常一律拒绝，不把失败扫描改PASS。保留原始内核字节，继续使用双DSO序号修复后的监督器。

新组件保留锁/租约时可接收root所有、只准finish_only、绑定本次boot/window/PID/startticks/租约及未来30秒有效期的显式恢复请求。仍须worker正常退出、无设备用户、默认PL/GDM和所有权全部成立，才由管理器自己归档租约、关闭自己的锁并正常退出；请求不能新增计算或结束在途worker。详见`platform/qwen35/a12/README_CLOSEOUT_V2.md`。

5项Linux PC策略/原生pidfd与真实文件锁测试通过；7项最终Window v2 PC测试通过，覆盖瞬时/持续扫描失败、危险状态拒绝、锁保留、错误/过期/扩大请求拒绝及受控正常退出。最终v2源码由唯一生成器复现并与测试源码摘要一致。**v2完整管理器/BOARD生命周期尚未执行**，未来新包必须显式引用并重新审核；当前实板成功来自专项恢复器，不冒充v2管理器板验。

原始首次不完整扫描没有保存，无法事后确认具体进程或缺项；“GDM恢复时进程变化”仍只是推测。此修复解决了检查记录与恢复入口缺口，不伪造旧原因证据。

## 成果及范围

新证据目录`evidence/model_pl_A/20261024-step07-finalize-v1/`包括EXPECTED、精确脚本、命令收据、执行前/后清单、逐事件日志、信号/退出证据、归档摘要、独立及延时复核、5+7项PC测试、AUDIT、FAILURES和封存清单。一个本地未执行v2草稿与独立派生审计失败也已保留，最终生成器/测试修正通过；没有因此重跑板测。

板上仅新增`/var/lib/kv260-a12/step07-finalize-20261024-v1`收尾记录、传输归档、一个已释放的协调锁文件，并产生旧wrapper的真实退出记录/历史租约归档。不覆写模型、旧包、公共契约或默认配置；不升级依赖、不重启、不刷写、不推送、不启用子代理。模型设置unknown。

两个第06步历史FAIL按用户要求继续保留待统一评估，本轮未扩大验证。下一步仅依据新的范围授权和新鲜前置决定；不得重放旧PID/旧租约/本次收口脚本。
'''
    (OUT/'REPORT.md').write_text(text,encoding='utf-8',newline='\n')
    header='2026-10-24 A12专项收口已完成：新鲜证实旧27132仅持锁等待且无子进程/XRT/设备后，一次pidfd定向SIGKILL结束（真实-9保留）；新finalizer正常exit0，旧租约原字节归档、双锁释放，独立及延时复核默认PL/GDM正常、无设备用户/ZOCL/active lease/相关进程。新增计算/PL装卸/服务改变/重启0。单投影既有PASS保留，三个投影/08未执行；首次收口FAIL与06两项FAIL保留。新增Window v2完成7项PC恢复测试，BOARD未测。报告 `evidence/model_pl_A/20261024-step07-finalize-v1/REPORT.md`。下方STOPPED/持锁等为历史快照。'
    p=ROOT/'docs/PROJECT_STATUS.json';old=json.loads(p.read_text(encoding='utf-8'))
    new={'role':old['role'],'a12_step07_finalize_20261024':status};new.update({k:v for k,v in old.items() if k!='role'})
    new['stage']='A12';new['stage_status']='IN_PROGRESS_SINGLE_PROJECTION_PASS_RECOVERY_CLOSEOUT_COMPLETE_MLP_UNTESTED'
    p.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for name in ('docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md'):
        p=ROOT/name;lines=p.read_text(encoding='utf-8').splitlines(keepends=True);lines.insert(1,'\n'+header+'\n')
        p.write_text(''.join(lines),encoding='utf-8',newline='\n')
    p=ROOT/'docs/AI_ASSISTANCE.md';lines=p.read_text(encoding='utf-8').splitlines(keepends=True)
    lines.insert(1,'\n2026-10-24 沿用xilinx-suite及固定SSH流程执行用户授权的收口，不扩大计算。实际模型设置unknown，无子代理/凭据落盘/依赖升级/提交推送。先PC真实子进程与锁测试、新鲜板端门禁后仅一次pidfd定向结束已无设备的等待manager；原-9与所有失败保留，独立/延时读回成功。'+header+'\n')
    p.write_text(''.join(lines),encoding='utf-8',newline='\n')
    p=ROOT/'docs/A12_STEP_PLAN_20261023.md';s=p.read_text(encoding='utf-8');lines=s.splitlines(keepends=True);lines.insert(1,'\n'+header+'\n');s=''.join(lines)
    start=s.index('### 07｜');end=s.index('### 08｜');part=s[start:end]
    part+='2026-10-24 专项恢复完成：\n\n- [x] 单投影旧窗口隔离锁租约完成专项收口；旧manager实际-9、首次正常收口失败保留，不追认为正常退出。独立及延时复核通过。\n- [ ] 三投影MLP的新范围计算/正常生命周期尚未执行，本轮不扩大。\n\n'
    s=s[:start]+part+s[end:];s+='\n## 10. 第07步专项收口更新\n\n'+header+'\n'
    p.write_text(s,encoding='utf-8',newline='\n')
    handoff=ROOT/'docs/handoffs/A_A12_STEP07_FINALIZE_COMPLETE_20261024.md'
    with handoff.open('x',encoding='utf-8',newline='\n') as f:f.write('# A12 单投影专项收口交接\n\n'+header+'\n\n当前无待收口板端进程/锁/active lease（以最后独立及延时快照为准）。不要重放旧PID、租约或此次恢复脚本。单投影3次真实调用和逐位数值/消费证据仍见旧封存目录；旧27132强制定向结束为-9，不能改成正常退出。新版Window v2为独立PC验证组件，未来新包必须显式引用、固定摘要与新审核；本轮没有启动它的BOARD计算生命周期。两个06历史FAIL、三投影/完整模型/性能验收继续独立。\n')
    print(json.dumps(dict(status=status['status'],new_computation=0,stage07_complete=False)))


if __name__=='__main__':main()
