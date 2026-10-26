"""Seal actual PC work, append own governance entry, preserve older evidence."""
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil

from health_fence_evidence import ROOT,OUT,PRIOR,read,save,sha,pin

KEY='a12_fresh_health_fence_pc_20261026'
HANDOFF='docs/handoffs/A_A12_FRESH_HEALTH_FENCE_PC_20261026.md'
DOCS=('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md')


def main():
    baseline=read(OUT/'BASELINE.json');old_status=read(OUT/'PROJECT_STATUS.before.json')
    assert (ROOT/'docs/PROJECT_STATUS.json').read_bytes()==(OUT/'PROJECT_STATUS.before.json').read_bytes()
    unchanged=[]
    for row in baseline['files']:
        if row['path'] in {'docs/'+n for n in DOCS}:continue
        p=ROOT/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],row['path']
        unchanged.append(row)
    original=read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/BASELINE.json')
    for row in original['parent_files']:
        p=Path(original['parent_bundle'])/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    for row in original['contract_files']:
        assert sha(row['path'])==row['sha256']
    assert all(r['exit_code']==0 for r in read(OUT/'GOVERNANCE_CHECKS.json')['commands'])
    assert read(OUT/'NATIVE_AUDIT.json')['status']=='PASS'
    assert 'Ran 34 tests' in (OUT/'pc-tests-03.txt').read_text() and (OUT/'pc-tests-03.txt').read_text().rstrip().endswith('OK')
    assert 'Ran 4 tests' in (OUT/'frozen-gate-tests-02.txt').read_text() and (OUT/'frozen-gate-tests-02.txt').read_text().rstrip().endswith('OK')
    strict=read(OUT/'run-health-strict-02/RESULT.json');request=read(OUT/'run-health-request-02/RESULT.json')
    reopen=read(OUT/'run-health-reopen-02/RESULT.json')
    pairs=[]
    for index,name in enumerate(('app_R0','app_hit')):
        s=strict['timing_PC_ONLY'][index];r=request['timing_PC_ONLY'][index];o=reopen['timing_PC_ONLY'][index]
        pairs.append(dict(id=name,strict_first_token_s=s['TTFT_app_ms']/1000,
            request_first_token_s=r['TTFT_app_ms']/1000,strict_validated_answer_s=s['complete_app_ms']/1000,
            request_validated_answer_s=r['complete_app_ms']/1000,
            request_log_delta_s=(s['complete_app_ms']-r['complete_app_ms'])/1000,
            reopen_validated_answer_s=o['complete_app_ms']/1000,
            FD_reuse_observed_delta_ms=o['complete_app_ms']-r['complete_app_ms'],
            one_pair_PC_only=True,p95=None,board_expected_saving_s=None))
    save(OUT/'TIMING_COMPARISON_PC_ONLY.json',dict(status='OBSERVED_ONE_SAMPLE_PER_MODE',pairs=pairs,
        owner_check_total_ms=dict(persistent=request['permission_metrics']['owner_check_ms'],
            reopen=reopen['permission_metrics']['owner_check_ms']),
        independent_monitor_is_not_proven_faster_than_old_synchronous_health=True,
        limitation='Same frozen question, sequential PC runs; no randomized/repeated trial or board prediction'))
    save(OUT/'ACTIVATION.json',dict(production_default=False,board_binding=False,
        board_contacted=False,compute_authorized=False,platform_released=False,
        old_resource_package_replaced=False,old_B_and_public_ABI_modified=False,
        board_recovery='OUT_OF_SCOPE',BOARD='NOT_TESTED',board_latency_saving_s=None,
        candidate_parameters_PC_ONLY=dict(interval_ns=250000000,max_age_ns=250000000,timeout_ns=1000000000),
        parameters_are_not_board_safety_approval=True))
    completion=read(PRIOR/'COMPLETION_AUDIT.json')
    for r in completion['requirements']:
        if r['id']=='P1-2':r.update(offline='FRESH_FD_IO_AND_INDEPENDENT_FENCES_REAL_PC_VALIDATED',
            real_PL_controller_binding='NOT_IMPLEMENTED',periodic_snapshot_reuse='NOT_ENABLED',
            safety_parameters='PC_EXPERIMENT_ONLY_BOARD_RESPONSE_REQUIREMENTS_STILL_REQUIRED',evidence=HANDOFF)
    completion.update(previous_turn_classification='progress',current_turn_classification='progress',
        whole_goal_achieved=False,goal_status='active',
        next_safe_action='Implement PC microbatch local budget/revocation/restart tests; keep real PL binding and mode transition separately reviewed',
        no_board_action_or_new_compute_authorization=True)
    save(OUT/'COMPLETION_AUDIT.json',completion)
    report='''# A12 P1-2 新鲜检查与独立监测：真实 PC 验证（2026-10-26）

本轮完成新的无板候选和真实 CPU 调用链验证，总目标仍 active。没有连接、恢复、部署或释放板卡，没有推送。原普通 R0/warm/hit 资源探测包保持原样；板端首次验证仍使用它。候选不进入默认服务或原板测包。

## 检查位置与失效语义

`fresh_identity_io.py` 只把只读 FD、固定缓冲区和初始身份准备移到初始化。可变租约类文件每次仍重新读完字节、计算 SHA，必要时逐字节比较，并前后核对 canonical inode/extent/metadata；映射表每次 seek 后重新扫描。没有 mtime/inotify 结论缓存。真实 mmap 第二次写入的测试保留了相同时间戳，但新摘要仍拒绝；真实进程后来加载改名的无害 CPU ELF，也能被已打开的 maps FD 检出。实际 Board 的双锁、租约与路径信任绑定尚未实现，PC 私有锁/身份 fixture 不能代替它。

`health_fence.py` 用一个独立线程采样，固定 64 条元数据环、最多两个协议线程/等待者，每份观测至多 8192 字节。监测线程不写日志；状态锁中不等待磁盘或 socket。每次 fence 必须取得**开始时间晚于本次请求**的新观测，拒绝旧快照复用。票据绑定实例代次、线程和序号且只能消费一次。缺失、丢序、异常、停摆、过期、重复票据均锁存失败。挂住的回调不能被 Python 强制终止；有界 join 未结束就明确报告线程仍活着，不声称安全释放。

`native_health_fence.py` 派生于冻结的请求日志入口。保留逐投影 IPC/顺序/预算；在日志完成后、发送允许回复前再次裁决故障、取消和 deadline；在 END/回执后、交付完整结果前再次裁决。裁决是已授权/在途的串行化边界，之后发生的故障不能被说成“瞬时撤销已发许可”或“取消 DMA”。故障先锁存再尽力记录，不因记录阻塞而继续发新许可，已扣预算不退还、不重放。

当前 250ms 空闲采样/最大票据年龄、1s 等待上限仅用于 PC 实验。旧 HealthSchedule 的 250ms 是空闲轮询参数，**没有授权按这个周期复用许可健康结论**；新增时限也是更严的候选约束，不能当成已经通过的 Board 安全参数。没有引入附件建议的 1s/3s 门槛。真实 PL 外层、kmsg 完整原件交接、资源/双锁接线和失调度响应仍需独立完成；本轮没有用新线程包装原带日志 I/O 的 Board health 回调来假称完成迁移。

## 已完成的验证

- 历史契约保护、新版配置检查 exit0，旧 DRAFT/BOARD 状态保持。
- 当前 23 项新测试通过，另 15 项已有 health/receive 回归通过。覆盖新鲜 fence、采样跨请求竞态、旧/伪造/跨线程票据、慢日志并发故障、采样停摆、取消/过期/隔离、END 后故障、mmap/替换/截断、maps 跨块与真实映射变化。冻结函数体/纯 gate 使用私有 PC 输入：原 MemAvailable≥1114112KiB、CmaFree≥98304KiB、0<温度<55000mC、BO 不重复扣费、boot/kmsg 连续性和新 WARNING 拒绝保持。
- 共 9 个开发/最终真实模型窗口：5 个正常三请求窗口、4 个故障窗口。最终当前源码有严格/请求日志/重新打开身份三个正常窗口及两故障窗口。正常窗口各 2880 次真实 CPU 投影、72 次权重加载、2959 次所有权检查、2958 个新鲜 fence 与授权；额外空闲采样单独计数。输出 token、文本、EOS、末位置 logits 指纹和清理状态与原 CPU 及 R0/hit 相同；不代表完整中间状态或 PL 数值验收。
- 首提交日志 append 阻塞时注入监测故障：已扣许可 1，实际 CPU started/completed 均 0，原生 ERROR 不交付。END append 阻塞时注入：已完成 1440 次 CPU 计算，原生 OK 且清理，但已核验答案交付数仍 0。实际原 append 在故障锁存后完成，保留那条 allow/END 候选记录；它不等于已发许可或已交付。故障进程均 EOF 合作 exit2，无强杀，不记正常关闭或板端释放。
- 原生 stdout、原请求日志链、回执、计数与新增 fence 时序独立对账通过。审计只给 PC 原件/计数一致结论，始终不允许释放或重放；完整文件仍不能证明过去 fsync 的成功。

早期测试中出现一次 fixture 对 SimpleNamespace 使用 super() 的错误，修为真实子类实例后通过；当时源码和失败日志保留。首版审计对 NTFS 镜像使用 Linux 私有目录门槛而被拒绝；没有放宽门槛，改为审计原私有 WSL worker 目录，再验证镜像逐文件 SHA 一致。两次失败均保留。底层原生程序、CPU 数学库、B 核和公共 ABI 均未修改/重编译。

## 输入后得到答案的耗时

同一个冻结问题、当前新检查链、每模式一次 PC 样本：

| 路径 | 严格日志：完整核验答案 | 请求日志：完整核验答案 | 内部首 token（请求日志） |
| --- | ---: | ---: | ---: |
| R0 | 10.945s | 5.938s | 4.781s |
| 70-token 公共前缀命中 | 5.483s | 2.892s | 1.736s |

严格/请求日志仍分别 2962/82 条，各有 4 份回执。完整答案计时包含内容检查及 END/回执；内部首 token 不能在内容检查前直接视为可交付回答。模型/权重启动及 Session 构造在这些请求计时之外。此处继续使用原普通前缀，没有新增长前缀、全位置 logits 或原始状态诊断文件，也没有重读旧 519.70MiB 原件。

相同请求日志/新安全链，只把每次重新打开改成 FD 复用，R0 6.016→5.938s、hit 2.970→2.892s，单个答案约 0.08s；全窗口所有权检查累计 1972.6→1704.8ms。该小差值只是顺序单样本观察，不是统计保证。独立线程逐次唤醒也有开销，本轮未证明它比旧同步 health 更快；新链比上一轮还多了 fresh 文件/maps 检查，不能直接把跨轮时间差归因给监测线程。此次主要已见收益仍来自请求日志，后续主要优化方向为受约束微批许可，不能靠继续省掉安全观测凑速度。

这些数值不是 A53/PL 预测、p95、语音端到端或生产 SLA；Board 时延/CMA 收益保持 null/NOT_TESTED。新时限/独立监测尚不默认启用。短提示词三组原 20/25、20/25、21/25 仍 NOT_ACCEPTED，不混入普通包。

## 剩余工作与证据

接续 P1-3 无板微批本地预算、失联/撤销/重启及未知在途证明；真实 PL 控制端独立未绑定接线与 P1-4 模式切换/严格回退也未完成。随后才是恢复且确认安全释放后的原严格普通资源基线、适用数值门禁、同工作量 A/B、长期稳定和最终验收。不能说只剩上板。

关键原件：本轮 `NATIVE_AUDIT.json`、`TIMING_COMPARISON_PC_ONLY.json`、`pc-tests-03.txt`、`frozen-gate-tests-02.txt`、`run-health-*/HEALTH_FENCE.json`、`native-transcripts-v2/`。逐命令、退出码和哈希见 `FINAL_REVIEW.json`；完整剩余要求见 `COMPLETION_AUDIT.json`。原 ZIP、父包 168 文件、前轮源码/失败与公共契约继续校验。复杂设计、核心逻辑和验收未委派 DeepSeek/子代理，实际模型设置 unknown。
'''
    with (ROOT/HANDOFF).open('x',encoding='utf-8') as f:f.write(report)
    updates={
        'DESIGN_GAP': '\n\n## 2026-10-26 P1-2 新鲜检查与独立监测 PC 候选\n\nFD/缓冲复用仍逐次全字节与 maps 检查；独立新鲜 fence、发送及 END 后故障关口已接真实 CPU 模型。23 项新增+15 项相关回归及最终真实模型/故障审计通过。Board 双锁/租约/kmsg 接线、时限依据、微批预算与撤销/重启、模式切换和最终验收未完成。候选不启用默认或替换原普通包；详情 `'+HANDOFF+'`。\n',
        'DECISIONS': '\n\n## 2026-10-26 A12 新鲜 fence 边界\n\n不缓存可变租约/映射结论；复用只读 FD 和缓冲。每许可仍要求本次之后开始的观测，独立监测不写日志；许可日志后与 END/回执后再次裁决，故障先锁存再记录。250ms/1s 仅 PC 实验，不能把原空闲轮询周期解释为许可复用授权。原探测包和默认保持，P1-3 后续推进。证据 `'+HANDOFF+'`。\n',
        'TEST_MATRIX': '\n\n## 2026-10-26 P1-2 PC 实测\n\n当前新测试23项（14文件/监测+5边界+4原判据 fixture）和15项已有相关回归通过；9个真实CPU模型窗口含5正常、4故障，最终当前源码3正常/2故障均独立对账。日志阻塞故障：首提交已扣1但实际0；END已算1440但0交付。CPU EOF exit2不记正常关闭/Board释放。首次fixture错误与NTFS私有目录审计拒绝保留，未降门槛。Board/CMA/最终数值与性能NOT_TESTED/null。证据 `'+HANDOFF+'`。\n',
        'AI_ASSISTANCE': '\n\n## 2026-10-26 独立健康监测无板候选\n\n新鲜FD读取、独立监测及最终许可/结果裁决由主代理实现，未委派核心/验收，未使用DeepSeek；模型设置unknown。当前38项测试和9个真实CPU窗口独立对账，未上板/部署/恢复/推送。当前PC完整答案严格→请求日志：R0 10.945→5.938s、hit 5.483→2.892s；同新链FD复用仅约0.08s/答案，单样本不作Board预测。未证明独立监测本身更快；目标active，P1-3/PL绑定/模式与最终验收仍待完成。交接 `'+HANDOFF+'`。\n'}
    for name,text in updates.items():
        p=ROOT/('docs/'+name+'.md');before=(OUT/(name+'.before.md')).read_bytes()
        assert p.read_bytes()==before
        with p.open('a',encoding='utf-8') as f:f.write(text)
    entry=dict(status='REAL_PC_FRESH_HEALTH_FENCES_VALIDATED_NOT_ENABLED',report=HANDOFF,
        final_review='evidence/model_pl_A/20261026-health-fence-v1/FINAL_REVIEW.json',
        new_tests=23,related_regression_tests=15,real_PC_native_windows=9,final_normal_windows=3,
        final_fault_windows=2,per_success_actual_CPU_calls=2880,fresh_fences_per_success=2958,
        final_PC_single_sample_timings=pairs,production_default=False,BOARD='NOT_TESTED',
        real_PL_binding='NOT_IMPLEMENTED',board_CMA='NOT_TESTED',board_latency_saving_s=None,
        goal_status='active',remaining='P1-3; real PL binding; P1-4; short prompt quality; final acceptance')
    state={KEY:entry,**old_status}
    (ROOT/'docs/PROJECT_STATUS.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert {k:v for k,v in read(ROOT/'docs/PROJECT_STATUS.json').items() if k!=KEY}==old_status
    save(OUT/'PRESERVATION.json',dict(status='PASS',unchanged_baseline_files=unchanged,
        original_parent_files_verified=len(original['parent_files']),original_contract_files_verified=len(original['contract_files']),
        old_status_entries_exact=True,old_governance_text_preserved_as_prefix=True,
        original_resource_ZIP_sha256=sha(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip')))
    sources=['fresh_identity_io.py','health_fence.py','native_health_fence.py','native_health_run.py',
        'native_health_audit.py','test_health_fence.py','test_health_boundaries.py','test_frozen_health_fence.py',
        'health_fence_evidence.py','health_fence_closeout.py']
    snapshot=OUT/'source-final';snapshot.mkdir(exist_ok=False)
    for name in sources:shutil.copyfile(ROOT/'platform/qwen35/a12'/name,snapshot/name)
    commands=[]
    def command(cmd,code,log,scope):commands.append(dict(command=cmd,exit_code=code,log=log,scope=scope))
    command('wsl -d KV260-A-2204 -- python3 platform/qwen35/a12/test_health_fence.py',0,'pc-tests-01/unittest.txt','PC fixtures and actual private file/maps I/O')
    command('wsl -d KV260-A-2204 -- python3 platform/qwen35/a12/test_frozen_health_fence.py',0,'frozen-gate-tests-01/unittest.txt','Frozen predicate private PC fixtures')
    for number,code in [('02',1),('03',0)]:
        command('wsl -d KV260-A-2204 -- python3 -m unittest discover -s platform/qwen35/a12 -p test_health*.py -v',code,'pc-tests-'+number+'.txt','PC fixture error preserved then corrected')
    command('wsl -d KV260-A-2204 -- python3 -m unittest discover -s platform/qwen35/a12 -p test_frozen_health_fence.py -v',0,'frozen-gate-tests-02.txt','Current frozen predicate fixtures')
    for tag,mode,fault,identity in [('health-request-01','request',None,None),('health-strict-01','strict',None,None),
            ('health-fail-permit-01','strict','permit_log',None),('health-fail-end-01','request','end_log',None),
            ('health-strict-02','strict',None,None),('health-request-02','request',None,None),
            ('health-reopen-02','request',None,'reopen'),('health-fail-permit-02','strict','permit_log',None),
            ('health-fail-end-02','request','end_log',None)]:
        cmd='wsl -d KV260-A-2204 -- python3 platform/qwen35/a12/native_health_run.py --mode '+mode+' --tag '+tag
        if fault:cmd+=' --fault '+fault
        if identity:cmd+=' --identity-mode '+identity
        command(cmd,1 if fault else 0,tag+'.txt','Real native PC model; injected refusal expected' if fault else 'Real native PC model')
    tags='health-request-01 health-strict-01 health-fail-permit-01 health-fail-end-01 health-strict-02 health-request-02 health-reopen-02 health-fail-permit-02 health-fail-end-02'
    for log,code in [('native-audit.txt',1),('native-audit-02.txt',0)]:
        command('wsl -d KV260-A-2204 -- python3 platform/qwen35/a12/native_health_audit.py '+tags,code,log,'Original private native transcript audit; NTFS rejection retained')
    evidence=[p for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    review=dict(status='PC_FRESH_HEALTH_FENCE_VALIDATED_GOAL_ACTIVE',recorded_at=datetime.now(timezone.utc).isoformat(),
        source=[pin(ROOT/'platform/qwen35/a12'/n) for n in sources],
        evidence=[pin(p) for p in evidence]+[pin(ROOT/HANDOFF)]+[pin(ROOT/'docs'/n) for n in DOCS],
        commands=commands,governance_commands='GOVERNANCE_CHECKS.json',
        new_tests=23,related_regression_tests=15,BOARD='NOT_TESTED',PL_calls=0,hardware_completions=None,
        board_latency_saving_s=None,board_CMA='NOT_TESTED',production_default=False,
        whole_goal_achieved=False,goal_status='active',actual_model_settings='unknown',
        DeepSeek_used=False,core_design_or_evidence_delegated=False,remote_pushed=False)
    save(OUT/'FINAL_REVIEW.json',review)
    print(json.dumps(dict(status=review['status'],source_files=len(review['source']),evidence_files=len(review['evidence']),
        new_tests=23,regression_tests=15,normal_windows=5,injected_fault_windows=4,old_parent_files=168,goal_status='active'),indent=2))


if __name__=='__main__':main()
