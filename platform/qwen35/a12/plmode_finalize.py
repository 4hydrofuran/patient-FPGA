"""Seal PL-mode no-board progress and audit remaining original requirements."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from plmode_evidence import ROOT,OUT,PARENT,DOCS,read,save,sha,pin

KEY='a12_pl_mode_offline_20261026'
HANDOFF='docs/handoffs/A_A12_PL_MODE_OFFLINE_20261026.md'

def local(path):
    text=str(path).replace('\\','/')
    return ROOT/text[len('C:/Patientqwen/'):] if text.startswith('C:/Patientqwen/') else Path(path)

def main():
    review=read(OUT/'ARTIFACT_REVIEW.json');assert review['status']=='PASS_PREPARED_PL_MODE_OFFLINE_ONLY'
    package=read(OUT/'PACKAGE_REVIEW.json');assert sha(ROOT/package['archive']['path'])==package['archive']['sha256']
    for row in review['artifacts']:assert sha(row['path'])==row['sha256']
    baseline=read(OUT/'BASELINE.json')
    for row in baseline['files']:assert sha(ROOT/row['path'])==row['sha256']
    older=read(PARENT/'PRESERVATION.json')['old_source_pins']+read(PARENT/'FINAL_REVIEW.json')['source']
    for row in older:assert sha(ROOT/row['path'])==row['sha256']
    probe=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1';original=read(probe/'BASELINE.json')
    for row in original['parent_files']:assert sha(local(original['parent_bundle'])/row['path'])==row['sha256']
    for row in original['contract_files']:assert sha(local(row['path']))==row['sha256']
    assert sha(probe/'bundle-v2.zip')=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    for label,script in [('HISTORICAL_CONTRACT_GUARD','scripts/release/check_contracts.py'),('QWEN35_CONFIG_GUARD','scripts/release/qwen35_config.py')]:
        cmd=[sys.executable,script];r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        save(OUT/(label+'.json'),dict(command=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));assert r.returncode==0
    activation=dict(BOARD='NOT_TESTED',ARM_execution='NOT_EXECUTED',board_operations=0,Board_lease_acquired=False,
        Board_provider_instantiated=False,actual_PL_results_consumed=False,production_enabled=False,SERVICE_ready=False,
        PL_mode='PREPARED_TYPED_BOARD_MANAGER_AND_SAME_PROCESS_COORDINATOR_NOT_BOARD_VALIDATED',
        default_backend='UNBOUND_UNSUPPORTED',candidate_backend='SEPARATE_REVIEW_ONLY_A53_BUILD_NOT_EXECUTED',
        ordinary_probe_replaced=False,release_authority=False,Board_CMA=None,Board_latency_saving_s=None)
    save(OUT/'ACTIVATION.json',activation)
    completion=read(PARENT/'COMPLETION_AUDIT.json')
    completion.update(previous_turn_classification='progress',current_turn_classification='progress',whole_goal_achieved=False,goal_status='active',
        audit_scope='ORIGINAL_P0_P1_REQUIREMENTS_PLUS_UNRESOLVED_CONTENT_AND_BOARD_ITEMS_NOT_PROJECT_WIDE_ACCEPTANCE')
    for row in completion['requirements']:
        if row['id'] in ('P1-1','P1-2','P1-3','P1-4','PL_BACKEND_LIFECYCLE','PL_MANAGER_PROTOCOL','GENERATION_CONSUMER'):
            for field in ('real_PL_controller_binding','real_PL_binding','board_device_generation_binding','real_runtime_manager_binding',
                'real_runtime_model_route_binding','device_generation_approval','live_Board_issuer'):
                if field in row:row[field]='PREPARED_TYPED_ORIGINAL_OWNER_SOURCE_NO_BOARD_EXECUTION'
            row['latest_evidence']=HANDOFF
        if row['id']=='P1-4':
            row.update(offline='ACTUAL_CPU_MODEL_MODE_HISTORY_NEW_INPUT_STRICT_FALLBACK_AND_ORIGINAL_OWNER_INTERFACE_PC_VERIFIED',
                production_mode_transition='NOT_ENABLED_REQUIRES_BOARD_ACCEPTANCE',service_request_routing='NOT_IMPLEMENTED_BOUNDED_ACCEPTANCE_ONLY')
        if row['id']=='PL_MANAGER_PROTOCOL':row['actual_model_route_hooks']='IMPLEMENTED_REAL_CPU_MODEL_PRIVATE_PROTOCOL_WITH_PREPARED_BOARD_PROVIDER'
    completion['requirements'].append(dict(id='PL_MODE_ORIGINAL_OWNER_INTEGRATION',offline='PREPARED_AND_TARGETED_PC_VALIDATED',evidence=HANDOFF,
        same_process_owner=True,original_asset_budget_gate='AST_UNCHANGED_ROOT_PC_FIXTURE_TESTED',
        original_owner_finish='UNCHANGED_AST_PC_PROCESS_FILESYSTEM_PROXY_ONLY',A53='TWO_BACKENDS_AND_READONLY_OBSERVER_CROSS_COMPILED_ONLY',BOARD='NOT_TESTED'))
    unresolved=[
        dict(id='SHORT_PROMPT_CONTENT',BOARD_required=False,status='UNRESOLVED_OFFLINE',
            work='Analyze all eight rejected IDs across the three frozen short-prompt variants; make any new candidate separately and retain all 25 fixed inputs, original EOS/content rules and failures. Do not change the ordinary package or use template fallback.'),
        dict(id='SERVICE_ROUTING',BOARD_required=False,status='SEPARATE_DESIGN_AND_IMPLEMENTATION_REMAINS',
            work='Interactive resident SERVICE and real application routing are not provided by the bounded three-request acceptance coordinator. Define separate lifecycle, per-request content/delivery gate and bounded resource accounting before claiming ready-for-use latency.'),
        dict(id='BOARD_FIRST_BASELINE',BOARD_required=True,status='DEFERRED_BY_USER',
            work='After separate fault recovery and independent safe release, fresh original identity/health/unique lease/dual locks and new compute authorization: run the unchanged ordinary R0/warm/hit package first.'),
        dict(id='BOARD_OPTIMIZED_ACCEPTANCE',BOARD_required=True,status='NOT_TESTED',
            work='Then separately review the prepared fixed-root runtime and live Owner binding, applicable full numerical/lifecycle checks, same-workload strict/batch A/B and resource stability; no automatic candidate activation.'),
        dict(id='FINAL_ACCEPTANCE_REVIEW',BOARD_required=True,status='INCOMPLETE',
            work='Actual input-to-accepted-answer timing, TT10/A12 step11, sustained behavior and medical/teacher review remain independent unpassed items. Repeated debugging is not acceptance evidence.')]
    completion.update(next_safe_action=unresolved[0]['work'],remaining=unresolved,
        no_board_action_or_new_compute_authorization=True,board_work_still_excluded=True,
        offline_core_candidate='P0_P1_PREPARATION_NOW_REVIEWABLE_NOT_ALL_PROJECT_OFFLINE_WORK_DONE')
    save(OUT/'COMPLETION_AUDIT.json',completion);save(OUT/'NEXT_WORK.json',dict(goal_status='active',remaining=unresolved,automatic_Board_action=False))
    prompt_path=ROOT/'evidence/model_pl_A/20261025-request-journal-v2/short-prompt-review-01/RESULT.json';prompts=read(prompt_path)
    assert [r['accepted'] for r in prompts['variants']]==[20,20,21] and all(r['adopt'] is False for r in prompts['variants'])
    audit_refs=[prompt_path,ROOT/'docs/A12_SAFETY_CHECK_OPTIMIZATION_PLAN_20261025.md',ROOT/'docs/A12_CMA_AWARE_ACCEPTANCE_ADJUSTMENT_20261025.md']
    for row in completion['requirements']:
        for field in ('evidence','latest_evidence'):
            if field in row and row[field]!=HANDOFF:
                path=ROOT/row[field];assert path.is_file();audit_refs.append(path)
    save(OUT/'REQUIREMENTS_AUDIT_SOURCES.json',dict(status='PASS_REFERENCES_AND_PRESERVED_UNPASSED_ITEMS',
        sources=[pin(p) for p in sorted(set(audit_refs))],short_prompt_acceptance=[20,20,21],short_prompt_denominator=25,
        whole_goal_achieved=False,all_offline_work_done=False,BOARD='NOT_TESTED'))
    report=f'''# A12 PL模式与原Owner接口：无板进展及剩余项（2026-10-26）

已完成本轮PL模式候选的无板接线、目标验证、A53交叉构建和审阅包。**尚不能说只剩上板**：新短提示词仍未通过内容门槛，常驻交互SERVICE及真实应用请求路由仍未实现；板端故障恢复、独立安全释放、性能和最终验收均没有新增通过结论。

## 本轮修改

协调器现在留在原Owner所在的父进程，原生worker为其直接子进程；沿用原租约与两把锁的同一open-file-description。另设明确CPUProvider和BoardProvider，PC JSON不能构造Board权限；Board路径要求原Owner、注册root ARM64和原有live-source门禁。正常native退出只进入等待原Owner.finish，不由新协调器恢复平台或释放设备。

启动前提取原start_worker的资产、模型完整SHA与预算检查，逆向AST相同，并安排在完整BO待分配准入之前。原CMA/内存/温度、日志连续性、IRQ、148 BO/72权重/140591104字节、8192对齐、低2GiB和5000次硬上限保留。使用普通前缀和有界日志，没有新增长前缀诊断、全位置logits/状态转储或历史原件扫描。

模式默认严格；空闲边界才允许选择微批。故障立即撤销授权，保留旧unknown/DIRTY和失败输入身份；PC只有持有pidfd确认真实子进程终止后，才允许显式新输入开启严格窗。Board失败保持隔离，恢复必须在本任务外完成，再由具有新租约、完整原门禁及明确恢复范围的原Owner绑定新的严格窗。没有自动恢复、重试、旧请求重放或CPU回退。

取消先撤销共享页再等待日志锁。若取消发生在private_closed已核验之后，保留关闭ACK握手使native正常退出，但窗口仍判失败。构造器拒绝不合法历史时只关闭本次本地FD，保留DIRTY及原日志；反例由3个遗留FD改为0。以上均不构成物理释放证明。

## 无板验证

- 最终normal04与fallback04的实际Qwen CPU模型原件独立审计通过：正常微批/严格窗各2880次实际CPU计算，grant分别40/2880；token、文本、EOS、末位置logits、warm快照摘要及清理/END/回执/交付门槛与冻结基线一致。失败窗第5次claim被拒绝，旧unknown不清；没有完整中间状态或真实PL结果通过结论。
- 22项元数据/历史策略测试、6项原资产门禁root PC夹具、原Owner worker/finalization接口的PC进程/文件系统代理、取消先于日志锁、关闭握手取消、只读页观察、5项重定位夹具与构造FD反例通过。Owner测试的默认PL检查为显式夹具，不能作为真实板端恢复或释放。
- BEGIN完整记录fsync失败在Popen前拒绝；原DIRTY保留、重启拒绝。干净历史重开默认严格，候选故障锁存和旧输入拒绝保持。
- 新A53 unbound/bound候选后端和只读observer交叉编译通过，未执行。后端相对父件只有3处可逆预处理门禁变化，XRT/BO/sync/start/meta/Y/timeout/poison与数学不改；导出符号与原私有/公共版本表一致，ARM无测试入口，observer只导出一个只读函数。
- 原CPU/native数学DSO、量化对象和A53数学DSO按原SHA复用。历史契约保护、新版配置校验均exit0，旧DRAFT/BOARD NOT_TESTED不追认。

早期构建锚点错误、DrvFs审计镜像权限拒绝、构造FD反例和所有开发模型记录均保留。最终模型证据为normal04/fallback04；其后构造器只改本地拒绝路径，单独验证了旧/新源码的实际FD差值，没有把较早模型实验冒称当前所有行都重跑。

## 交付与后续

审阅包：`{package['archive']['path']}`，SHA `{package['archive']['sha256']}`，逐成员CRC/SHA回读通过。它依赖冻结仓库、原native/math/model及另审固定根路径布局，不是独立部署包，不含模型/sidecar/bitstream或安装恢复、上板执行脚本。具体A53文件、SONAME别名和缺件/篡改拒绝检查见BOARD_BUILD-v2-complete.json及RELOCATION_TEST.json。

原普通资源包SHA仍为`acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`，将来首轮仍先运行它；不能直接用新候选替换基线。原失败、父包168文件、公共5契约及历史source/evidence保持性重新核对。

总审计将P0/P1离线准备与尚未完成项分别登记，见COMPLETION_AUDIT.json。三个短提示词仍为20/25、20/25、21/25，未采用。下一项可独立无板推进的是分析保留的8个失败ID并验证新候选，不能降门槛或修改原普通包；SERVICE必须单独设计与接线，三请求窗不代表可连续投入使用。

实际板端时延/CMA收益保持null，当前PC单样本不能推算“输入后几秒应答”。本轮不上板、不SSH、不恢复/释放、不推送。复杂设计、核心实现及验收未委派；DeepSeek未使用，实际模型/effort设置工具不可核实，记unknown。目标仍active。
'''
    with (ROOT/HANDOFF).open('x',encoding='utf-8') as f:f.write(report)
    for name in DOCS:shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.at-finalization'))
    current=read(ROOT/'docs/PROJECT_STATUS.json');assert KEY not in current
    entry=dict(activation,status='PL_MODE_PREPARED_PC_VALIDATED_A53_COMPILED_ONLY',evidence=HANDOFF,goal_status='active',whole_goal_achieved=False)
    final=dict(current);final[KEY]=entry;(ROOT/'docs/PROJECT_STATUS.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary='PL模式与同进程原Owner/双锁/启动资产门禁/最终worker接口候选已接；最终实际CPU模型普通与故障后新输入严格窗、独立审计、A53构建及目标故障用例通过。Board未执行，unknown/DIRTY和原门槛保留，普通探测包不变。总审计仍列短提示词内容及常驻SERVICE/应用路由缺口，不能称只剩上板；目标active。'
    for name in DOCS[1:]:
        with (ROOT/'docs'/name).open('a',encoding='utf-8') as f:f.write('\n\n## A12 PL模式无板进展与总审计（2026-10-26）\n\n'+summary+' 见 `'+HANDOFF+'`。\n')
    assert {k:v for k,v in read(ROOT/'docs/PROJECT_STATUS.json').items() if k!=KEY}==current
    for name in DOCS[1:]:assert (ROOT/'docs'/name).read_bytes().startswith((OUT/(name+'.at-finalization')).read_bytes())
    save(OUT/'PRESERVATION.json',dict(status='PASS',baseline_source_evidence_files=len(baseline['files']),old_source_pins=older,
        original_parent_files=len(original['parent_files']),contracts=len(original['contract_files']),other_status_entries_exact=len(current),
        current_governance_preserved_as_prefix=True,original_probe_sha256=sha(probe/'bundle-v2.zip'),board_contacted=False,pushed=False))
    sources=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').iterdir()) if p.is_file() and p.name.startswith(('plmode_','test_plmode_'))]
    evidence=[pin(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('FINAL_REVIEW.json','TERMINAL_VERIFICATION.json')]
    governance=[pin(ROOT/'docs'/name) for name in DOCS]+[pin(ROOT/HANDOFF)]
    save(OUT/'FINAL_REVIEW.json',dict(status='PASS_PL_MODE_PREPARATION_OFFLINE_SCOPE_ONLY',source=sources,evidence=evidence,governance=governance,
        BOARD='NOT_TESTED',whole_goal_achieved=False,all_offline_work_done=False,goal_status='active'))
    for row in sources+evidence+governance:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
    save(OUT/'TERMINAL_VERIFICATION.json',dict(status='PASS_ALL_LISTED_CURRENT_BYTES',pins_verified=len(sources+evidence+governance),
        final_review_SHA256=sha(OUT/'FINAL_REVIEW.json'),whole_goal_achieved=False,goal_status='active',BOARD='NOT_TESTED'))
    print('PASS_ALL_LISTED_CURRENT_BYTES',len(sources+evidence+governance))
if __name__=='__main__':main()
