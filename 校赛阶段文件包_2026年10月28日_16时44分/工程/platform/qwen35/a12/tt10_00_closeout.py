"""Publish only after independent TT10-00 BOARD audit; retain unrelated status."""
import datetime
import hashlib
import json
from pathlib import Path
from tt10_00_prepare import ROOT,OUT,j,save,sha


def capture_before(path, raw):
    target=OUT/'before-closeout'/path.relative_to(ROOT)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream:stream.write(raw)


def main():
    board=j(OUT/'BOARD_AUDIT.json');assert board['task00_complete'] and board['actual_PL_calls']==9360
    for name in ('contracts_final.json','config_final.json','analyze_01.json'):
        assert j(OUT/'logs'/name)['exit_code']==0
    measured=j(OUT/'BOARD_BASELINES.json');rows=measured['rows'];pc=j(OUT/'PC-02.json')
    original=j(OUT/'PROTECTED_BEFORE.json')
    assert all(sha(ROOT/p)==v['sha256'] for p,v in original.items())
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    summary=dict(status='PASS_TT10_00_FROZEN_AND_BOUNDED_BOARD_BASELINES',updated_beijing=now,
        task00_complete=True,real_inputs=25,original_17_preserved=True,policy_inputs=7,neutral_prefix_tokens=70,
        actual_uncached_R0_tokens='105-116 in frozen corpus',prospective_suffix_tokens='35-46 after neutral prefix; not yet reused',
        PC_checks=pc['count'],real_PC_application_requests=4,BOARD_actual_PL_calls=9360,
        BOARD_application_measurements=len(rows),ordinary_samples_per_mode_backend=2,
        ordinary_BOARD_PL_TTFT_app_s={mode:[r['TTFT_app_s'] for r in rows if r['mode']==mode and r['side']=='s2' and not r['profile']] for mode in ('health','cpu02')},
        BOARD_initial_postcheck_failures=1,BOARD_precompute_manager_refusals=1,
        CROSS_BUILD='NOT_REQUIRED_UNCHANGED_A53',cache_restore='NOT_IMPLEMENTED',TTFT10_goal='NOT_MET_R0_BASELINE',
        next='TT10-01 exact full-state prefix snapshot/restore',default_FPGA_enabled=False,A12_step11='PENDING',
        rollback='/var/lib/kv260-a12/cpu02-candidate-20261024-v1',actual_model_settings='unknown',subagents=0)
    save(OUT/'SUMMARY.json',summary)
    failures=[dict(kind='PACKAGER_SYNTAX',log='logs/package_01.json',resolution='Closing bracket corrected before any board action'),
              dict(kind='HOST_AUTH_HELPER_BUILD_PATH',exit_code=1,resolution='Forward-slash csc source argument corrected; auth_helper_build_02 exit0'),
              dict(kind='PREBOARD_REVIEW_OBSERVER_AVAILABILITY',snapshot='preboard-review01',resolution='Original health baseline cannot provide new detailed manager spans; mark unavailable and retain aggregate/native only'),
              dict(kind='AUTH_CANCELLED',receipt='preflight_01/receipt.json',payload_sent=False,board_compute_started=False,resolution='User closed window; new readonly authentication/preflight_02 succeeded'),
              dict(kind='DEPLOYED_PARENT_MANIFEST_REVIEW',snapshot='preboard-review02',resolution='CPU02 readback has refreshed control/preflight.json; all other files match; pin actual deployed/readback manifest, preserve original source manifest'),
              dict(kind='AD_HOC_DOCUMENT_FREEZE_SYNTAX',resolution='Unmatched brace in stdin preparation script; no files written; reproducible tt10_00_freeze.py then exit0')]
    failures.append(dict(kind='FIRST_HEALTH_INDEPENDENT_POSTCHECK_FAILED',receipt='board_01/receipt.json',manager_exit=0,actual_PL_calls_completed=4680,
        exact_initial_subcondition='UNKNOWN_NOT_CAPTURED_BY_ORIGINAL_DRIVER',resolution='Read-only postcheck_inspect_01 proved normal release; fresh complete and delayed rechecks passed in board_02; health compute not replayed; no force cleanup',
        changes='Continuation adds a bounded 5-second settle before cpu02 independent postcheck and emits gate summary; all gate predicates unchanged'))
    failures.append(dict(kind='CPU02_V1_OWNER_INITIAL_PROCESS_SCAN_REFUSED',receipt='board_02/receipt.json',manager_exit=1,
        exception='PROCESS_SCAN_INCOMPLETE_OR_WRONG_BOOT',exact_initial_scan_issue='UNKNOWN_NOT_CAPTURED_BY_PARENT',
        failed_readback='cpu02/failed-readback-v1',compute_workers_started=0,PL_mutations=0,PL_calls=0,
        resolution='Read-only scene in board_03 proves no lease/lock/module and normal default PL/GDM; original failed package retained. One independent v2 window adds only initial scan persistence before the same require_no_users check; no predicate relaxed and no automatic retry.',
        review='CPU02_RETRY_REVIEW.json'))
    save(OUT/'FAILURES.json',dict(failures=failures,BOARD_compute_failures=0,BOARD_precompute_manager_refusals=1,BOARD_initial_postcheck_failures=1,violations_10s=[r for r in rows if r['violation_10s']],
         violations_are_expected_unoptimized_baseline=True))
    report=['# TT10-00：真实短输入、应用计时与对照冻结完成','',f'日期：{now}。状态：**PASS_TT10_00_FROZEN_AND_BOUNDED_BOARD_BASELINES**。','',
        '本阶段完成无板准备和必要有界BOARD基线；前缀缓存尚未实现，当前R0结果不满足10秒目标。未把基线冻结等同于加速达标。','',
        '## 冻结内容','',
        '- 原17条开发模型请求与8条变体，共25条真实输入；7条策略响应分账。原17条提示词/token与00封存逐字节一致，全部25条经PC及两版S1/S2原生分词核对。',
        '- 真正稳定中性前缀70token；原17条共同71token中有1token属于问题开头。中性前缀后35—46token，现阶段仍全部R0重算105—116token。',
        '- TTFT_app从实际Session.submit接收文本之前到原生首token接收，包括路由、提示词/Jinja构造和原生分词。正常EOS、内容检查和语音指标分开。',
        '- 固定原健康版及02版的模型/sidecar/程序/库/SDK/线程/配置；两版native ARM与父级完全相同。原健康V1、新02 V2剖面分别读取。普通模式关闭细分观察，安全检查/fsync保持。',
        f'- {pc["count"]}项最终PC适配/边界检查通过，前后两轮共4次真实PC应用请求；没有新ARM交叉构建。HOST凭据窗口小程序编译不计ARM构建。','',
        '## BOARD实测','',
        '| 版本 | 后端 | 请求 | 普通/剖面 | 应用TTFT秒 | worker首token秒 | 生成完成秒 | 内容检查完成秒 |',
        '|---|---|---|---|---:|---:|---:|---:|']
    for r in rows:report.append(f'| {r["mode"]} | {r["side"]} | {r["id"]} | {"剖面" if r["profile"] else "普通"} | {r["TTFT_app_s"]:.3f} | {r["TTFT_worker_s"]:.3f} | {r["generation_complete_app_s"]:.3f} | {r["validated_complete_app_s"]:.3f} |')
    report+=['','每版、每后端仅2次普通和1次剖面真实自然请求；9token teacher代理与完整数值诊断另列。固定先健康版后02版，文件cache不保证冷，不作统计显著/p95或总体加速验收。原52.624秒/02旧50.701秒是历史worker口径，不能替代本次应用计时。','',
        '## 数值、安全、资源与恢复','',
        '- 两个窗口各4680真实PL调用，总9360，均在5000次独立租约上限内。旧/新同后端及各自S1/S2的443份投影、logits和混合状态二进制文件逐位一致；自然回答token、EOS、最后prompt logits与应用事实检查通过。',
        '- 每次许可拥有唯一新鲜健康观察；原管理器安全类/main AST、逐次fsync实现及父级原生库保留。两个完成计算的窗口worker/manager均正常exit0。健康版首次独立检查失败，原始失败保留且精确子条件未知；随后只读复核及追加独立/延时检查通过，没有重放健康版计算。',
        '- CPU02 v1在创建租约前因PROCESS_SCAN_INCOMPLETE_OR_WRONG_BOOT拒绝，尚未启动worker或修改PL；原扫描未保存细节，不能追认为已知瞬态。只读复核干净后另开v2窗口，仅在同一初始扫描与原拒绝谓词之间增加明细保存，检查条件原样保留。失败v1及回执保留，未强杀、重启或强制清理。v2正常计算、释放及独立/延时检查通过。',
        '- 实际装载库路径/hash见BASELINES_BOARD_IDENTITY.json；worker RSS、148 BO/140591104字节、短序列完整状态和诊断/日志磁盘占用见RESOURCE_ACCOUNTING.json。CPU图工作区没有单独分配器口径，仅包含在worker RSS；其拆分、XRT隐式资源、完整系统物理峰值及未来快照可用余量仍null。',
        '- TT10-01暂按2个64MiB快照槽及64MiB恢复工作区共192MiB作规划预留；不是已准入内存。精确边界/全上下文状态与恢复峰值需在TT10-01实测。','',
        '## 失败、回退和下一步','',
        '上板前组包/诊断归属/父级manifest差异审查及取消认证的原件、日志均保留，见FAILURES.json、preboard-review01/02及preflight_01。认证取消未发送板端payload。CPU02部署manifest只有control/preflight.json合法刷新，其他父级条目逐字节相同；实际部署/readback身份独立固定。',
        'TT10测量包位于独立板端目录tt10-00-health-20261024-v1及tt10-00-cpu02-20261024-v2，失败的cpu02-v1保留；原CPU02选择与各历史回退未覆盖。传输采用固定host key的SSH内存流，凭据仅隐藏输入/内存传递，不含密码日志；PACKAGE中的gzip上传路径是准备参考，本次未执行SCP上传。',
        '**下一步TT10-01：以70token真实中性前缀建立完整状态快照，验证恢复后与同输入R0的数值/混合状态等价，再测真实少算量与应用TTFT。** 不提前执行TT10-02/03或改默认后端。A12第11步PENDING；A13进度保留。实际模型/推理设置unknown，无子代理、无push。','']
    (OUT/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
    plan=ROOT/'docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md';plan_before=plan.read_bytes();capture_before(plan,plan_before);text=plan_before.decode('utf-8')
    text=text.replace('状态：**计划已建立，优化实现及新性能验收尚未开始**。','状态：**TT10-00已完成无板准备与有界实板基线；下一项TT10-01，前缀缓存尚未实现**。',1)
    start=text.index('### TT10-00｜');end=text.index('### TT10-01｜',start)
    part=text[start:end].replace('- [ ]','- [x]')
    part+='**2026-10-24执行记录：TT10-00完成。** 25条真实输入/7条策略分账，原17条字节不变；中性前缀70token、后缀35—46token。27项最终PC检查和4次实际PC应用请求，两个BOARD窗口9360真实PL调用及数值/正常恢复通过。应用计时、两个R0对照和预算已冻结，详见[阶段报告](../evidence/model_pl_A/20261024-ttft10-00-v1/REPORT.md)。10秒目标尚未达到，TT10-01未实施。\n\n'
    text=text[:start]+part+text[end:]
    text=text.replace('**下一项为TT10-00，随后TT10-01。**','**当前下一项为TT10-01；TT10-00实际完成记录见第4节。**')
    text=text.replace('## 8. 本次建立计划的实际产物与下一步','## 8. 计划建立时的记录与当前下一步\n\n以下为计划创建时快照；后续TT10-00实测见第4节执行记录。')
    assert plan.read_bytes()==plan_before,'concurrent plan update'
    plan.write_text(text,encoding='utf-8')
    note='## 2026-10-24 TT10-00输入、计时与R0对照冻结完成\n\n25条真实问题与7条策略响应分账，原17条提示词/token字节不变；确认中性前缀70token、变化后缀35—46token。最终27项PC检查及两轮4次真实PC请求；健康版/02版独立BOARD窗口9360真实PL调用，443份投影/logits/混合状态逐位一致、应用事实检查和正常释放/独立延时恢复通过。TTFT_app包含实际路由、模板与原生分词，普通/剖面分开；基线R0未达10秒，缓存仍NOT_IMPLEMENTED。CROSS_BUILD为NOT_REQUIRED_UNCHANGED_A53，下一项TT10-01；默认后端不改、A12第11步PENDING、A13既有条目保留。报告 `evidence/model_pl_A/20261024-ttft10-00-v1/REPORT.md`，输入/计时/对照与预算均已封存。\n\n'
    note+='健康版首次独立后检失败及02首次创建租约前扫描拒绝均保留；精确初始子条件未保存，记UNKNOWN，不追认为已知瞬态。只读复核后分别追加后检、独立v2窗口，未放宽门槛或强制清理。\n\n'
    for rel in ['docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md']:
        p=ROOT/rel;old=p.read_bytes();capture_before(p,old)
        assert p.read_bytes()==old,'concurrent documentation update: '+rel
        p.write_bytes(note.encode('utf-8')+old)
    save(ROOT/'docs/handoffs/A_A12_TT10_00_20261024.json',dict(status=summary['status'],plan='docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md',
         report='evidence/model_pl_A/20261024-ttft10-00-v1/REPORT.md',next=summary['next'],rollback=summary['rollback'],caveats=measured['caveats']))
    state=ROOT/'docs/PROJECT_STATUS.json';current=state.read_bytes();data=json.loads(current)
    capture_before(state,current)
    data={'a12_ttft10_00_20261024':dict(summary,report='evidence/model_pl_A/20261024-ttft10-00-v1/REPORT.md'),**data}
    assert state.read_bytes()==current,'concurrent update: rerun status-only merge with latest data'
    state.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=summary['status'],next=summary['next'])))

if __name__=='__main__':main()
