"""Record an incomplete stage at user-requested end; no board access or tests."""
import datetime,json
from tt10_01_common import ROOT,OUT,j,save,sha


def main():
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    for rel,pin in j(OUT/'PROTECTED_BEFORE.json').items():assert sha(ROOT/rel)==pin
    for directory in ('worker','worker-resume'):
        rows=[json.loads(s) for s in (OUT/'pc-diagnostic-04'/directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        assert rows[-1]['event']=='WORKER_EXITED_NORMALLY' and rows[-1]['exit_code']==0
    scene=j(OUT/'scene_01/stdout.txt');isolation=scene['files']['run-v1/s2/ISOLATED.json']['json']
    numeric=j(OUT/'pc-diagnostic-04/NUMERICAL.json');assert numeric['equal']
    summary=dict(status='INCOMPLETE_USER_ENDED_ROUND_BOARD_SCENE_RETAINED',updated_beijing=now,task01_complete=False,
        source03=dict(model_PC_checks=89,component_checks=15,real_application_pairs=25,cancel_PC='PASS',A53_build='PASS',
                      model_quality_pass=23,model_quality_rejected_same_R0_and_hit=['V07','V08']),
        BOARD=dict(status='ISOLATED_DURING_CPU_DIAGNOSTIC',actual_PL_calls=0,TTFT_app_s=None,
                   reason=isolation['reason'],manager_pid=167484,cpu_worker_pid=167575,
                   last_scene_CmaFree_kib=52816,original_required_CmaFree_kib=98304,exact_rejection_instant_value=None,
                   lease_retained=True,normal_release_and_GDM_restore='NOT_COMPLETED',
                   recovery_authorization='USER_DECLINED_FOR_NOW_RETAIN_SCENE',recovery_executed=False,
                   outer_controller='Existing bounded monitor may remain waiting until its original 2100-second deadline; no new computation'),
        source04=dict(change='Owned diagnostic file fsync+DONTNEED only; computation/state logic unchanged',PC_build='PASS',
                      actual_file_IO_checks=7,prefill_diagnostic_chunk=8,
                      saved_numerical_gate=dict(equal=True,projection_streams=144,full_logits=108,state_equal=True),
                      final_PC_reaudit='INCOMPLETE_HARNESS_FAILURE',A53_build='NOT_RUN',BOARD='NOT_TESTED',deployed=False),
        new_failures=[dict(log='logs/diagnostic_pc_01.json',cause='Wrong reference path after numerical gate; worker normal exit0'),
                      dict(log='logs/diagnostic_pc_02.json',cause='Saved JSON vs regenerated gate equality assertion; detailed diagnosis pending; worker normal exit0')],
        protected_sources_unchanged=True,default_backend_changed=False,TTFT10_goal='NOT_VERIFIED_NO_NEW_BOARD_TIMING',
        next=['Preserve board scene until user authorizes recovery; do not run recovery script automatically',
              'Fix source04 verification harness (check JSON integer/string map keys), complete ordinary application checks and A53 build',
              'Implement and test CPU failure normal close/finalization with fresh closing-only observations; keep compute health latch',
              'Prepare independent new package/window only after recovery; retain original failed window and all thresholds',
              'Finish actual PL numerical/TTFT/normal restore audit before marking TT10-01 complete'],
        TT10_02='NOT_STARTED',A12_step11='PENDING',actual_model_settings='unknown',subagents=0)
    save(OUT/'PROGRESS.json',summary)
    report=f'''# TT10-01 本轮停止点（未完成）

记录时间：{now}。用户要求尽快结束本轮开发；停止新增实现/构建/测试。**TT10-01尚未完成，不能标记BOARD通过或10秒达标。**

## 已完成

- source-03精确70token完整状态与独立logits快照/恢复：15项组件、89项完整模型检查、25对实际应用输入R0/hit一致性、取消与错误身份验证通过；固定2026.1 A53构建通过。
- 25条输入中23条模型内容检查通过，V07/V08两侧模型输出均被原检查拒绝并模板回退；原例、阈值和质量失败保留。
- source-04仅修订原始诊断文件写入：新建独占文件完整写入、fsync后DONTNEED，不改模型数学、状态逻辑或许可日志。PC构建和7项实际文件I/O检查通过。8token分块诊断已保存144条投影流、108个完整logits及混合状态一致的NUMERICAL.json。
- source-04汇总复核未完成：首次路径错误；修正后第二次在保存JSON与重新计算gate比较处断言失败。可能涉及JSON整数键转字符串，需要后续确认。两次本地native均正常exit0；未启动source-04 A53构建或新板测包。

## 板端现场（按用户要求保留）

首SSH等待认证时关闭，payload未发送。第二连接启动独立窗口后，在CPU诊断阶段触发原`HealthBlocked: full-model live extra reserve gate`；尚未进入PL，新增PL调用0，**没有本轮TTFT测量结果**。

只读现场MemAvailable 2987932 KiB、CmaFree 52816 KiB；原计算门槛1114112/98304 KiB。精确拒绝瞬间数值原管理器未保存。CPU worker日志显示前缀捕获成功、工作状态已清空并等待stdin；监管器已停泊并保持租约。旧终结接口没有登记这个CPU worker，无法正常finalize。

恢复提案`RECOVERY_PROPOSAL.md`与`tt10_01_recover.py`已准备；**用户明确暂不恢复，故从未执行**。没有终结进程、归档/删除租约、卸载模块、刷写或重启。正常释放和桌面服务恢复尚未完成。现有外层监测可能继续等待其原2100秒有界期限，不追加计算；相关stdout/receipt仍可能变化，因此本阶段不生成最终SEAL。

## 后续必须接续

1. 在用户明确授权前保留板端现场，不自动执行恢复脚本。旧失败包和租约不能重用或删除。
2. 复核source-04测试脚本的JSON键类型/对照路径，完成普通应用检查，再A53构建。不能把此前89项源于source-03的检查写成全部在source-04重跑。
3. 实现并验证CPU阶段失败的合作取消、正常退出与关闭专用新鲜检查；不清除计算健康锁存、不修改原PL未知DMA隔离。
4. 恢复后另建独立新窗口，验证CMA真实余量、S1/S2完整数值、普通应用TTFT和正常恢复。DONTNEED只是建议，目前未证明能解决板端CMA问题。
5. 全部板验通过后才完成TT10-01；TT10-02未开始。原01A/03、公共契约、生产选择及既有回退均保留，A12第11步PENDING，A13条目不覆盖。

证据入口：PROGRESS.json、PC_AUDIT_FINAL.json、STATE_API_AUDIT.json、DERIVATION-03/04.json、scene_01、logs/diagnostic_pc_01/02.json、pc-diagnostic-04/NUMERICAL.json。未执行的analyze/closeout/final_check脚本是先前准备草稿，仍针对失败窗口；不能直接用于追认通过。
'''
    (OUT/'PROGRESS.md').write_text(report,encoding='utf-8')
    save(OUT/'FAILURES_PROGRESS.json',dict(status='INCOMPLETE_FAILURES_PRESERVED',
        inherited=['logs/build_pc_01.json','logs/pc_01.json','logs/pc_02.json','PC_PAUSE_REQUEST.json','board_01/receipt.json'],
        board_isolation=isolation,scene_receipt='scene_01/receipt.json',new_failures=summary['new_failures'],
        quality_rejections=['V07','V08'],recovery_executed=False))
    note=f'## 2026-10-25 TT10-01本轮结束，BOARD隔离现场保留（未完成）\n\nsource-03的15项组件、89项完整模型、25对真实输入一致性及A53构建通过；V07/V08模型质量拒绝保留。首次BOARD在CPU诊断阶段因原CMA/内存余量门槛隔离，新增PL调用0、TTFT为null，租约/监管器保持，正常释放/桌面恢复未完成。用户明确暂不恢复、保留现场，随后要求尽快结束本轮；没有执行恢复或强杀。source-04诊断资源修订PC构建/7项I/O检查及已保存数值gate通过，但汇总脚本两次失败仍需处理，未做新A53/BOARD。TT10-01不能标完成，TT10-02未开始；默认选择不改，A12第11步PENDING，A13旧条目保留。接续见 `evidence/model_pl_A/20261024-ttft10-01-v1/PROGRESS.md`。\n\n'
    def snapshot(rel,raw):
        p=OUT/'before-checkpoint'/rel;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    for rel in ('docs/status/A.md','docs/DESIGN_GAP.md'):
        p=ROOT/rel;old=p.read_bytes();snapshot(rel,old);assert p.read_bytes()==old;p.write_bytes(note.encode('utf-8')+old)
    rel='docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md';p=ROOT/rel;old=p.read_bytes();snapshot(rel,old)
    text=old.decode('utf-8').replace('状态：**TT10-00已完成无板准备与有界实板基线；下一项TT10-01，前缀缓存尚未实现**。',
        '状态：**TT10-00完成；TT10-01无板主体通过、首次BOARD在CPU阶段隔离，用户要求保留现场；本阶段未完成**。',1)
    at=text.index('### TT10-02｜')
    text=text[:at]+'**2026-10-25停止点：TT10-01未完成。** 无板主体与A53构建通过；BOARD在CPU诊断时触发原余量门禁，新增PL调用0、TTFT为null。用户暂不恢复并要求结束本轮，现场/租约保持。source-04诊断资源修订及测试汇总仍有待完成项；保持本节复选框未勾选，接续见[本轮进度](../evidence/model_pl_A/20261024-ttft10-01-v1/PROGRESS.md)。\n\n'+text[at:]
    assert p.read_bytes()==old;p.write_text(text,encoding='utf-8')
    rel='docs/PROJECT_STATUS.json';p=ROOT/rel;old=p.read_bytes();snapshot(rel,old);data=json.loads(old)
    assert 'a12_ttft10_01_in_progress_20261025' not in data
    data={'a12_ttft10_01_in_progress_20261025':dict(summary,report='evidence/model_pl_A/20261024-ttft10-01-v1/PROGRESS.md'),**data}
    assert p.read_bytes()==old;p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save(ROOT/'docs/handoffs/A_A12_TT10_01_IN_PROGRESS_20261025.json',dict(summary,report='evidence/model_pl_A/20261024-ttft10-01-v1/PROGRESS.md'))
    save(OUT/'LOCAL_STOP_CHECK.json',dict(status='LOCAL_TEST_WORKERS_NORMAL_EXIT_REMOTE_SCENE_RETAINED',
        protected_sources_unchanged=True,local_worker_exits=[0,0],new_tasks_started=False,recovery_executed=False,
        task01_complete=False,report_sha256=sha(OUT/'PROGRESS.md'),active_board_artifacts_not_sealed=True))
    print(json.dumps(dict(status=summary['status'],task01_complete=False,local_worker_exits=[0,0])))


if __name__=='__main__':main()
