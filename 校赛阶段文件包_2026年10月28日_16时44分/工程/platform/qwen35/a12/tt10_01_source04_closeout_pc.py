"""Summarize the bounded source04 PC continuation; never finalize TT10-01/BOARD."""
import datetime
import difflib
import json
from tt10_01_common import ROOT,OUT,j,sha,save


def main():
    base=OUT/'source04-continuation-20261025-v1'
    pc=j(OUT/'PC_DIAGNOSTIC_04.json');run=OUT/pc['run_directory']
    assert pc['status']=='PASS_SOURCE04_DIAGNOSTIC_IO_AND_CHUNK8_NUMERICAL'
    assert pc==j(run/'PC_DIAGNOSTIC_04.json') and all(c['passed'] for c in pc['checks'])
    receipts=['tt10_01_continue_contracts_01','tt10_01_continue_config_01','diagnostic_regression_03','diagnostic_pc_04','build_arm04_01']
    for name in receipts:assert j(OUT/'logs'/(name+'.json'))['exit_code']==0,name
    before=j(base/'BEFORE.json');changed=[]
    for name,pin in before['protected'].items():
        p=ROOT/name
        if not p.is_file() or p.stat().st_size!=pin['bytes'] or sha(p)!=pin['sha256']:changed.append(name)
    for name,digest in j(OUT/'PROTECTED_BEFORE.json').items():
        if sha(ROOT/name)!=digest:changed.append(name)
    assert not changed,changed
    for name,digest in j(OUT/'DERIVATION-04.json')['sources'].items():assert sha(OUT/'source-04'/name)==digest
    inputs=j(base/'SOURCE04_BUILD_INPUT_AUDIT.json')
    assert inputs['source04_evidence_matches_derivation'] and inputs['source04_workspace_matches_derivation']
    assert inputs['PC_binary_sha256']==pc['native_sha256']
    arm=OUT/'build-arm04';flags=(arm/'flags.make').read_text();elf=(arm/'arm-elf.txt').read_text()
    assert '-mcpu=cortex-a53' in flags and '-march=native' not in flags and 'SP_A12_PC_TEST' not in flags
    assert 'AArch64' in elf and 'ELF64' in elf
    build=dict(status='PASS_CROSS_BUILD_ONLY',domain='CROSS_BUILD',SDK='2026.1',CPU='cortex-a53',BOARD='NOT_TESTED',executed_on_board=False,
        native_sha256=sha(arm/'qwen35-a12'),files={p.name:sha(p) for p in arm.iterdir() if p.is_file()},receipt='logs/build_arm04_01.json')
    save(OUT/'BUILD_ARM_04.json',build)
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    failures=[]
    for name in ('diagnostic_pc_01','diagnostic_pc_02','diagnostic_pc_03'):
        p=OUT/'logs'/(name+'.json');r=j(p);assert r['exit_code']==1
        failures.append(dict(receipt=str(p.relative_to(OUT)),exit_code=r['exit_code'],sha256=sha(p)))
    summary=dict(status='PASS_SCOPED_SOURCE04_NO_BOARD_VALIDATION_TT10_01_INCOMPLETE',updated_beijing=now,task01_complete=False,
        source04_PC=pc,harness_regression=j(base/'HARNESS_REGRESSION.json'),A53=build,
        raw_evidence_preservation=dict(status='PASS',protected_files=len(before['protected']),baseline_sha256=sha(base/'BEFORE.json'),changed_files=changed),
        failures_retained=failures,additional_baseline_capture_failure='source04-continuation-20261025-v1/BASELINE_CAPTURE_ATTEMPT_01.json',
        source03_model_rerun=False,source03_89_checks_reassigned=False,source03_historical_quality=dict(model_candidate_pass=23,rejected_same_R0_hit=['V07','V08'],clinical_review='PENDING_TEACHER_REVIEW'),
        BOARD=dict(status='NOT_ACCEPTED_PRIOR_CPU_WINDOW_ISOLATED',new_PL_calls=0,TTFT_app_s=None,live_state_rechecked=False,recovery_executed=False,source04='NOT_TESTED'),
        TTFT10_goal='NOT_VERIFIED',TT10_02='NOT_STARTED',A12_step11='PENDING',default_backend_changed=False,actual_model_settings='unknown',DeepSeek_used=False,
        remaining=['CPU-stage failure cooperative close/finalization and fresh closing-only health checks are not implemented/validated/deployed; compute latch and DMA isolation must remain',
            'Board scene/recovery remains deferred by user; prior SSH reset is not release evidence',
            'Source04 A53 binary has not run on board; DONTNEED does not prove CMA recovery',
            'New authorized independent board window still requires numerical, actual PL consumption, ordinary TTFT and full release/restore evidence',
            'Historical V07/V08 quality rejections and teacher review remain; 100-request/10-second acceptance not performed'],
        receipts={name:dict(path='logs/'+name+'.json',sha256=sha(OUT/'logs'/(name+'.json'))) for name in receipts})
    save(OUT/'SOURCE04_NO_BOARD_SUMMARY.json',summary)
    timing=pc['ordinary_timings']
    report=f'''# TT10-01 source-04 无板验证接续结果

北京时间：{now}。维护者 A。**本轮限定的 source-04 无板验证通过；TT10-01 未完成，BOARD 未验收，实板 TTFT 为 null，未证明 ≤10 秒。**

已核对并保留 diagnostic_pc_01/02 两次失败及全部原始文件。第二次失败确认为 logits 位置字典键在内存为 int、JSON 中为 str，全部键和值经 JSON 往返后相等。另发现旧 pc-run-04/BOUNDARY_70.json 不含完整摘要字段，改从 source-03 已有原始文件只读重算；没有重跑 source-03 模型，没有把其 89 项通过重记为 source-04。

新入口强制指定独立 --run，并以 --reuse-diagnostics 只读引用既存诊断，不再用 --resume 重用 worker/请求目录。结果在新目录 {pc['run_directory']}。新增 diagnostic_pc_03 失败因本轮把 443 个二进制文件误计为总文件数，实际另有 1 个 manifest、共 444 个文件；逐文件哈希全部相等。该错误已纠正，失败回执和当时工具源码保留，未启动该次模型。

实际通过：历史/新版契约检查各 1 项；验证脚本 {summary['harness_regression']['count']} 项回归；source-04 {pc['count']} 项检查（含现存原始诊断复核及新增模型检查）。legacy 的 443 个二进制文件及 manifest 全部相同；144 条完整投影流、108 个完整 logits 向量、混合状态在 R0/恢复以及 source-03/source-04 之间摘要全部相同。逐字节摘要比较无数值容差；单字节改动、缺失/重复位置、截断和缺失状态字段负例均拒绝。

普通应用只补跑冻结输入 {pc['ordinary_input_id']} 的 1 对 R0/hit，真实执行 Session 路由、模板、原生分词和原内容检查。结果 token/text、完整最后位置 logits SHA、混合状态指纹一致，两侧 MODEL、自然 EOS、原内容检查通过。R0 新算 {timing[0]['cache']['new_tokens']} token；hit 复用 {timing[1]['cache']['reused_tokens']}、新算 {timing[1]['cache']['new_tokens']} token。PC TTFT_app 为 R0 {timing[0]['TTFT_app_ms']:.3f} ms、hit {timing[1]['TTFT_app_ms']:.3f} ms，仅为本机单对观测，不能用于实板 10 秒验收。另补 1 对零后缀自然生成，保存 logits/完整状态一致。新 worker 正常 exit0。

固定 2026.1 SDK、cortex-a53 的 source-04 交叉构建通过；ELF64/AArch64、编译和链接记录已保存，不含 -march=native 或 PC 故障注入宏。二进制 SHA256：{build['native_sha256']}。仅完成构建，未部署、未在 ARM/板端运行。

保留性检查：本轮基线 {len(before['protected'])} 个原始证据/源码文件逐项 SHA256 和长度不变，既有封存索引/契约/默认选择的既定保护项检查通过。没有修改 source-03/source-04 模型源码、公共数学/ABI 或原失败记录。原 25 对应用一致性仍归 source-03，23 条候选通过及 V07/V08 两条同侧质量拒绝保留；教师审核仍 PENDING。

剩余问题与建议顺序：先在新派生工具补 CPU 故障合作关闭/正常终结及独立新鲜关闭检查，保持计算健康锁存和未知 DMA 隔离；随后在用户另行授权恢复后核对准确板端现场并按实情恢复。当前不连接、不终结进程、不释放租约。之后才能准备独立新板测窗口，验收真实 PL 数值/消费、应用 TTFT、CMA 和完整正常释放/桌面恢复。DONTNEED 只是建议，CMA 问题尚未证明解决。source-04 取消/损坏等全套 89 项未重跑，历史 source-03 证据保留；新 CPU 终结通道测试另做。TT10-02 未开始，A12 第 11 步 PENDING，默认后端不变，A13 条目保留。

机器可读汇总：SOURCE04_NO_BOARD_SUMMARY.json。PC 明细：PC_DIAGNOSTIC_04.json；交叉构建：BUILD_ARM_04.json；命令/退出码：logs/diagnostic_pc_01.json 至 diagnostic_pc_04.json、diagnostic_regression_03.json、build_arm04_01.json。完整命令、退出码与各回执 SHA 见机器汇总。此报告不是整体 SUMMARY/SEAL 或 BOARD_AUDIT。
'''
    path=OUT/'SOURCE04_NO_BOARD_REPORT.md'
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write(report)
    for name in ('tt10_01_diagnostic_pc.py','tt10_01_numeric.py'):
        a=(base/'before/platform/qwen35/a12'/name).read_text(encoding='utf-8')
        b=(ROOT/'platform/qwen35/a12'/name).read_text(encoding='utf-8')
        with (base/(name+'.patch')).open('x',encoding='utf-8') as f:
            f.writelines(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='before/'+name,tofile='after/'+name))
    print(json.dumps(dict(status=summary['status'],checks=pc['count'],preserved_files=len(before['protected']),report=str(path)),ensure_ascii=False))


if __name__=='__main__':main()
