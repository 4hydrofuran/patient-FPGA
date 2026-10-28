"""Publish TT10-01 actual evidence after independent gates, preserving shared docs."""
import datetime,json
from tt10_01_common import ROOT,OUT,FROZEN,j,save,sha


def capture(rel,raw):
    dest=OUT/'before-closeout'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(raw)


def main():
    board=j(OUT/'BOARD_AUDIT.json');assert board['task01_complete']
    for name in ('analyze_01','contracts_final','config_final'):
        assert j(OUT/'logs'/(name+'.json'))['exit_code']==0
    for rel,pin in j(OUT/'PROTECTED_BEFORE.json').items():assert sha(ROOT/rel)==pin
    assert j(OUT/'logs/build_arm_01.json')['exit_code']==0
    assert j(OUT/'PC_AUDIT_FINAL.json')['model_checks']==89
    timings=j(OUT/'BOARD_TIMINGS.json');resources=j(OUT/'RESOURCE_ACCOUNTING_BOARD.json')
    pc=j(OUT/'PC.json');quality=[r for r in pc['quality'] if r['answer_source']!='MODEL']
    assert [r['id'] for r in quality]==['V07','V08']
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    rows=timings['rows'];pl={r['id']:r for r in rows if r['side']=='s2'}
    work={name:j(OUT/'readback-v1/run-v1/s2'/name/'actual-work.json') for name in ('diag_exact','warm_prefix','diag_full_R0','diag_hit','app_R0','app_hit')}
    summary=dict(status='PASS_TT10_01_EXACT_PREFIX_STATE_AND_BOUNDED_BOARD',updated_beijing=now,task01_complete=True,
        prefix_tokens=70,PC_model_checks=89,PC_component_checks=15,PC_real_application_pairs=25,
        PC_model_answer_checks_pass=23,PC_model_answer_rejected_and_template_fallback=quality,
        BOARD_actual_PL_calls=board['actual_PL_calls'],BOARD_ordinary_pairs_per_backend=1,
        BOARD_PL_TTFT_app_s={k:v['TTFT_app_s'] for k,v in pl.items()},
        BOARD_PL_complete_app_s={k:v['complete_app_s'] for k,v in pl.items()},
        BOARD_PL_TTFT_reduction_fraction=timings['improvement']['s2']['TTFT_reduction_fraction'],
        actual_work=work,snapshot=resources['rows']['s2']['snapshot'],
        TTFT10_goal=board['TTFT10_goal'],CROSS_BUILD='PASS_EXISTING_2026_1_A53',
        implemented_in='Independent opt-in native worker + actual Session measurement adapter; production default unchanged',
        deployed_candidate=j(OUT/'PACKAGE-02.json')['remote'],
        next='TT10-02 input structure and suffix reduction; retain V07/V08 quality failures',
        rollback=board['rollback'],default_backend_changed=False,A12_step11='PENDING',actual_model_settings='unknown',subagents=0)
    save(OUT/'SUMMARY.json',summary)
    failures=[
        dict(kind='PC_BUILD_MISSING_OPENSSL_HEADERS',log='logs/build_pc_01.json',resolution='Reused installed libcrypto stable ABI with opaque declarations; no package install; final PC/A53 build exit0'),
        dict(kind='PC_IMPORT_PATH',log='logs/pc_01.json',resolution='Explicit project import path before model tests'),
        dict(kind='WSL_PYTHON310_FILE_DIGEST_UNAVAILABLE',log='logs/pc_02.json',resolution='Bounded streaming SHA helper; no Python upgrade'),
        dict(kind='USER_REQUESTED_PAUSE',record='PC_PAUSE_REQUEST.json',log='logs/pc_03.json',resolution='Controller interrupted at user request; native graceful shutdown exit0; user then requested resume, full pc_04 exit0'),
        dict(kind='AUTH_CONNECTION_CLOSED',receipt='board_01/receipt.json',payload_sent=False,board_compute_started=False,
             resolution='Old SSH connection closed while awaiting input; new explicit board_02 session authenticated, same script hash'),
        dict(kind='PC_MODEL_QUALITY_REJECTION',ids=['V07','V08'],details=quality,
             resolution='Unchanged R0 and cache generations both rejected by existing checker; TEMPLATE fallback retained. No corpus removal or threshold relaxation; carry to TT10-02')]
    save(OUT/'FAILURES.json',dict(failures=failures,BOARD_compute_failures=0,BOARD_restoration_failures=0,
        violations_10s=[r for r in rows if r['violation_10s']],clinical_review='PENDING_TEACHER_REVIEW'))
    report=['# TT10-01：精确前缀完整状态复用完成','',f'实际收口时间：{now}。状态：**{summary["status"]}**。','',
        '实现、无板一致性验证、A53交叉构建及独立有界板测已完成。候选部署于独立目录，原系统默认选择保持原状。TT10-01的退出条件是正确恢复、实际少算和TTFT改善；10秒总目标仍按实测单独判断。','',
        '## 实现','',
        '- 捕获完整attention KV、递归/卷积状态与位置/序列元数据。实际固定state API不保存logits，因此额外保存全部248320维最后位置logits，并用独立序列导出SHA核对恢复。零后缀也使用正确快照logits生成。',
        '- 仅按完整真实分词后的精确token前缀命中；CPU/PL键隔离，绑定模型/程序/关键实际装载库及模板、量化、布局、契约和运行配置。公共中性70token与私有病例/会话/epoch命名隔离；首版板端只启用中性公共前缀。',
        '- 2个64MiB槽和64MiB scratch上限，板测额外192MiB规划余量准入。响应后工作状态清空；取消/失败不提交会话终态，保留原清理、隔离及显式R0。损坏和部分恢复失败验证拒用并明确R0。',
        '- bridge epoch、job、许可、BO和设备所有权不进入快照。管理器安全类/main AST与父级相同；逐次新鲜健康、许可fsync、完整输出/meta、单在途及未知DMA隔离均保留。原01A、03和B交付不改。',
        '- 设计见 `design/qwen35/A12_TT10_01_PREFIX_STATE.md`；固定源码/补丁见source-03、DERIVATION-03和worker-prefix-03.patch，正式ARM候选不含PC故障注入接口。','',
        '## 无板与数值验证','',
        '- 15项真实C++组件检查、89项完整模型检查及25对实际应用输入R0/hit通过一致性比较。旧R0全部443份二进制诊断保持一致。70token边界拼接前后144条投影流、108个完整logits向量及混合状态逐位一致。',
        '- 覆盖新增后缀0/1/8/9/16/17/24/32/48、多次恢复、版本/前缀失配、损坏、部分恢复失败、病例/session/epoch切换、第三槽拒绝、1022/1023长上下文尾块、空输入/超界和合作取消。真实取消测试在PC CPU执行，未在板端注入DMA故障。',
        '- **质量限制：V07、V08在R0和缓存两侧均被原内容检查拒绝，最终按原规则返回TEMPLATE；其余23条模型回答通过检查。** 这证明缓存未改变结果，不等于25条模型回答质量全通过；两条原样保留并交给TT10-02回归，医学教师审核仍PENDING。',
        '- 固定2026.1 SDK、cortex-a53交叉构建通过，未升级依赖/运行时、未修改归约数学或public ABI。用户暂停导致的中断、正常native退出和随后完整重跑均保留。','',
        '## BOARD普通应用计时','',
        '每个后端只测1对普通R0/hit，固定先R0后hit；应用t0在Session.submit之前，包含路由、模板、原生分词、命中校验和恢复，到真实首token事件。重诊断单独执行。','',
        '| 后端 | 请求 | 应用TTFT秒 | 应用完成秒 | 新算token | 复用token | 恢复毫秒 |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        c=r['cache'];report.append(f'| {r["side"]} | {r["id"]} | {r["TTFT_app_s"]:.3f} | {r["complete_app_s"]:.3f} | {c["new_tokens"]} | {c["reused_tokens"]} | {c["restore_ms"]:.3f} |')
    report+=['',f'PL同轮应用TTFT降低 **{100*timings["improvement"]["s2"]["TTFT_reduction_fraction"]:.1f}%**。10秒目标状态：**{board["TTFT10_goal"]}**。这是一对描述性比较，不是p95、统计显著性或最终100请求验收。历史52.624秒和50.701秒是旧worker口径；本次以同输入、同轮应用口径为主要对照。','',
        '### 实际少算与启动成本','',
        '| 用例 | 新prefill token | prefill真实PL调用 | decode真实PL调用 | 本请求真实PL调用 |',
        '|---|---:|---:|---:|---:|']
    for name,w in work.items():report.append(f'| {name} | {w["new_prefill_tokens"]} | {w["prefill_PL_calls"]} | {w["decode_PL_calls"]} | {w["request_actual_calls"]} |')
    report+=['',f'本窗口合计 **{board["actual_PL_calls"]} 次真实PL调用**，包含前缀预计算和诊断，在5000次硬上限内。启动预计算648次调用不能从总量中隐去；每个后续命中才避免重复计算这些调用。','',
        '| 后端 | worker ready秒 | 前缀预计算秒 | service ready墙时秒 | 快照计费字节 | worker峰值RSS KiB |',
        '|---|---:|---:|---:|---:|---:|']
    for side,r in resources['rows'].items():report.append(f'| {side} | {r["worker_ready_wall_s"]:.3f} | {r["precompute_client_s"]:.3f} | {r["service_ready_wall_s"]:.3f} | {r["snapshot"]["charged_bytes"]} | {r["peak_worker_RSS_kib"]} |')
    report+=['','service ready墙时还包含本验证流程在预计算前执行的legacy诊断/分词审计，不能当作最小产品冷启动耗时；冷启动不承诺10秒。上述启动成本不计入热请求TTFT，服务在前缀完成后才声明ready。','',
        '## 板端验证、恢复与证据边界','',
        '- 同ARM新旧R0及S1/S2 legacy全部诊断一致；完整107token R0与恢复70+37后缀的每条投影流、108个logits向量、完整混合状态、最终状态指纹及普通自然输出一致。S1/S2完整原件每文件SHA也一致，不用PC与ARM跨ISA逐位比较替代。',
        '- 72份权重保持驻留，148显式BO/140591104字节保持不变；每次真实提交均有新的健康观察，剖面用例逐许可有一次record.fsync。worker与manager均正常exit0；独立和延时复核确认租约/锁/模块释放、默认overlay与GDM恢复。',
        '- 所有大投影/中间logits原件继续保留板端 `'+j(OUT/'PACKAGE-02.json')['remote']+'/run-v1`。本机回读保留legacy完整原件、混合状态、关键完整logits、每文件SHA、全部流式比对结果和全部安全日志；没有声称全部大文件已回传。',
        '- 资源详见RESOURCE_ACCOUNTING_BOARD：规划余量已做实际准入，快照与worker RSS有实测；XRT隐式资源、CPU图独立分配及完整系统物理峰值仍null。长上下文尾部通过不代表允许128token以上前缀快照。','',
        '## 回退及下一步','',
        '独立候选目录：`'+j(OUT/'PACKAGE-02.json')['remote']+'`。默认选择未改；原CPU02 `'+board['rollback']+'`、CPU01、健康版、TT10-00对照和显式R0均保留。SSH首连接在认证等待中关闭，payload未发送；第二连接使用同一脚本hash完成。失败记录详见FAILURES.json。没有强制清理、刷写、重启或远程push。','',
        '**下一项TT10-02：调整输入结构并缩短35—46token变化后缀，目标16—24token，同时回归V07/V08和完整事实检查。** 本轮没有提前修改提示词。严格10秒与最终全样本验收继续未完成；A12第11步PENDING，A13既有状态保留。实际模型设置unknown，无子代理。','']
    (OUT/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
    rel='docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md';path=ROOT/rel;old=path.read_bytes();capture(rel,old);text=old.decode('utf-8')
    text=text.replace('状态：**TT10-00已完成无板准备与有界实板基线；下一项TT10-01，前缀缓存尚未实现**。','状态：**TT10-01已完成精确前缀快照/恢复及有界板测；下一项TT10-02，严格10秒总目标仍未完成**。',1)
    start=text.index('### TT10-01｜');end=text.index('### TT10-02｜',start)
    part=text[start:end].replace('- [ ]','- [x]')
    part+=f'**2026-10-25执行记录：TT10-01完成。** 15项组件/89项完整模型检查、25对真实输入一致性、A53构建及{board["actual_PL_calls"]}次有界真实PL调用通过。同轮PL应用TTFT {pl["app_R0"]["TTFT_app_s"]:.3f}→{pl["app_hit"]["TTFT_app_s"]:.3f}秒，70token精确前缀恢复后只新算37token；完整状态/logits/投影与正常恢复通过。V07/V08两侧原模型质量拒绝及模板回退保留；10秒未达成，默认选择未改。详见[阶段报告](../evidence/model_pl_A/20261024-ttft10-01-v1/REPORT.md)。\n\n'
    text=text[:start]+part+text[end:]
    text=text.replace('**当前下一项为TT10-01；TT10-00实际完成记录见第4节。**','**当前下一项为TT10-02；TT10-00/01实际完成记录见第4节。**')
    assert path.read_bytes()==old;path.write_text(text,encoding='utf-8')
    note=f'## 2026-10-25 TT10-01精确前缀完整状态复用完成\n\n70token中性前缀完整状态+独立logits快照/恢复；15项组件、89项完整模型检查、25对实际应用输入一致性和A53构建通过。独立BOARD窗口{board["actual_PL_calls"]}次真实PL调用，S1/S2和R0/恢复数值一致，安全许可/fsync保留、正常退出及独立/延时恢复通过。PL普通应用TTFT {pl["app_R0"]["TTFT_app_s"]:.3f}→{pl["app_hit"]["TTFT_app_s"]:.3f}秒（每后端仅一对，固定顺序）；严格10秒未完成。V07/V08两侧模型输出均被原检查拒绝并模板回退，原例保留；23条通过模型质量检查，不将一致性等同全部质量通过。默认后端未改，下一项TT10-02；A12第11步PENDING，A13既有状态保留。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/REPORT.md`。\n\n'
    for rel in ('docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md'):
        path=ROOT/rel;old=path.read_bytes();capture(rel,old);assert path.read_bytes()==old;path.write_bytes(note.encode('utf-8')+old)
    save(ROOT/'docs/handoffs/A_A12_TT10_01_20261025.json',dict(summary,report='evidence/model_pl_A/20261024-ttft10-01-v1/REPORT.md',plan='docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md'))
    rel='docs/PROJECT_STATUS.json';path=ROOT/rel;old=path.read_bytes();capture(rel,old);data=json.loads(old)
    assert 'a12_ttft10_01_20261025' not in data
    data={'a12_ttft10_01_20261025':dict(summary,report='evidence/model_pl_A/20261024-ttft10-01-v1/REPORT.md'),**data}
    assert path.read_bytes()==old;path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=summary['status'],next=summary['next'])))


if __name__=='__main__':main()
