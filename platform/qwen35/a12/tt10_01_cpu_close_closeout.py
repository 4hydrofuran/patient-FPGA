"""Record PC-only close-channel evidence and merge latest shared project status."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import re
from tt10_01_common import ROOT,OUT,j,sha,save


def main():
    base=OUT/'cpu-close-20261025-v1';candidate=base/'manager-source-03'
    result=j(base/'pc-run-04/RESULT.json');derivation=j(base/'DERIVATION-03.json')
    assert result['status']=='PASS' and result['tests']==26 and result['real_source04_CPU_cases_passed']==2
    assert not result['failures'] and not result['errors']
    assert result['candidate_sources']==derivation['sources']
    for name,digest in derivation['sources'].items():assert sha(candidate/name)==digest
    assert sha(candidate/'tt10_01_cpu_close.py')==sha(ROOT/'platform/qwen35/a12/tt10_01_cpu_close.py')
    baseline=j(base/'BASELINE.json');changed=[]
    for name,pin in baseline['protected'].items():
        path=ROOT/name
        if not path.is_file() or path.stat().st_size!=pin['bytes'] or sha(path)!=pin['sha256']:changed.append(name)
    assert not changed,changed
    archive=j(base/'GENERATED_BYTECODE_ARCHIVE.json')
    for row in archive['files']:assert sha(row['original'])==sha(row['archive'])==row['sha256']
    parent=OUT/'candidate/bundle-v2'
    extras={str(p.resolve()) for p in parent.rglob('*') if p.is_file() and p.relative_to(ROOT).as_posix() not in baseline['protected']}
    assert extras=={row['original'] for row in archive['files']}
    rejected=j(base/'CACHE_CLEANUP_REJECTED.json');assert rejected['executed'] is False
    names=[n.name for c in ast.parse((ROOT/'platform/qwen35/a12/tt10_01_cpu_close_test.py').read_text()).body if isinstance(c,ast.ClassDef) and c.name=='Tests' for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
    index=(base/'TEST_NAME_INDEX.md').read_text(encoding='utf-8')
    rows=re.findall(r'^\| TC\d+ \| `([^`]+)` \|$',index,re.M)
    assert names[:25]==rows and len(names)==26
    with (base/'TEST_NAME_INDEX_FINAL.md').open('x',encoding='utf-8') as f:
        f.write(index+'\nTC26 为主代理后续补充的并发隔离回归：`'+names[25]+'`。全部结果见 pc-run-04/RESULT.json。\n')
    receipts=['cpu_close_contracts_01','cpu_close_config_01','cpu_close_derive_03','cpu_close_pc_04']
    for name in receipts:assert j(OUT/'logs'/(name+'.json'))['exit_code']==0
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    summary=dict(status='PASS_PC_CPU_CLOSE_CHANNEL_NOT_DEPLOYED',updated_beijing=now,task01_complete=False,
        PC=result,derivation=derivation,candidate_directory=candidate.relative_to(ROOT).as_posix(),
        source04_native_sha256=j(OUT/'PC_DIAGNOSTIC_04.json')['native_sha256'],source03_model_rerun=False,PL_supervisor_and_public_contract_unchanged=True,
        original_protected_files=dict(count=len(baseline['protected']),changed=changed,status='PASS_ORIGINAL_BYTES_UNCHANGED'),
        generated_bytecode=dict(count=len(extras),archived=True,also_left_in_original_parent=True,cleanup_review='REJECTED_blocked_by_policy',original_source_or_manifest_changed=False),
        cooperation=dict(normal_worker_exit=0,failed_manager_process_exit=1,failed_case_compute_pass=False,forced_termination=False,
            compute_latch_reset=False,late_output_usable=False,release_requires='normal exit, no quarantine/readers, fresh kernel/owner checks, complete scan, exact default/GDM checks, original atomic archive and locks'),
        evidence_scope='Linux children/flocks and two actual source04 CPU runs; all board/platform/GDM/kernel states are PC fixtures. Retention assertions precede test-only fixture teardown.',
        BOARD='NOT_TESTED',new_PL_calls=0,TTFT_board_s=None,board_connected=False,board_recovery_executed=False,board_recovery_authorized=False,
        independent_board_window_prepared=False,A53_rebuild='NOT_REQUIRED_PYTHON_CONTROLLER_ONLY',actual_model_settings='unknown',
        DeepSeek=dict(used=True,task='Format 25 fixed test names as Markdown only',thinking=False,requested_model='service default',actual_model='unknown',review='All 25 rows/names/order exact; primary agent designed and accepted tests',receipt='DEEPSEEK_FORMATTING_RECEIPT.json'),
        failed_attempts=[dict(log='logs/cpu_close_pc_01.json',exit_code=1,cause='DrvFS lock fdinfo does not prove Linux FLOCK ownership; no child launched; native WSL storage used without weakening checks'),
            dict(log='logs/cpu_close_pc_02.json',exit_code=1,cause='14/16 cases passed; post-close journal read error fixed in CPU-only get; unexpected-permission fixture wait corrected')],
        prior_pass=dict(log='logs/cpu_close_pc_03.json',tests=25,status='PASS_REVISION02',superseded_by='26-case revision03 adds quarantine-during-close guard'),
        receipts={name:dict(path='logs/'+name+'.json',sha256=sha(OUT/'logs'/(name+'.json'))) for name in receipts},
        next=['Keep existing board scene unchanged until separate recovery authorization; current board identity/process/lease remains unknown',
            'After authorized recovery and proven release/default restore, prepare a separately pinned independent package/window using source04 and this controller revision',
            'Run actual board CPU failure/normal close, PL numerical/consumption, application TTFT, CMA and full release/restore checks; retain original thresholds and 10-second goal',
            'TT10-01 completion, 100-request/10-second acceptance and V07/V08/teacher quality review remain outstanding'])
    save(base/'SUMMARY_PC.json',summary)
    report=f'''# TT10-01 CPU故障关闭通道：无板实现与验证

北京时间：{now}。维护者 A。**关闭通道已在独立管理器源码修订实现，26项PC测试通过；未部署、未连接板卡，TT10-01仍未完成。**

执行范围按用户最新授权与 docs/DEEPSEEK_SOL_COLLABORATION.md。主代理负责设计、核心实现、调试和证据验收；DeepSeek仅把25个已固定测试名称排成Markdown表格，thinking=false、请求服务默认、实际模型unknown；主代理逐项核对后保存，另补TC26。没有发送凭据、许可证、患者资料、完整仓库或核心逻辑，没有委派命令执行。

修订位于 `manager-source-03/`，由原candidate/bundle-v2的管理器独立派生。增加CPU-only worker权限拒绝、CPU启动前预留/启动后立即登记、完整CPU身份及FD/maps观察、合作SIGUSR1取消和一次stdin shutdown、正常退出/线程结束/无quarantine的关闭证明。构造不确定、身份/设备/权限异常、超时、坏退出、退出过程中新增quarantine、扫描不完整、内核/默认平台/GDM未证明均保留owner；不强杀、不清锁、不放宽未知DMA规则。

计算失败锁存保持。只有已登记子进程正常exit0且无隔离异常后，才绕开“计算调度器”的锁存，直接执行新的关闭专用内核/owner观察；这不会清除计算锁存或更新最后计算成功时间。原完整扫描、默认平台/GDM证明、原子归档与锁释放规则继续调用原Window实现。新PL构造一旦开始就不能回到CPU清理路径。原PL许可/BO/meta/fsync逻辑和公共数学/ABI未改。

低余量拒绝在抛错前独占写入并fsync原比较样本；测试保存CmaFree=52816 KiB、原门槛98304 KiB，以及MemAvailable=1114111 KiB拒绝，边界1114112/98304仍按原比较通过，没有更改门槛。新派生管理器的失败入口在成功清理后保存FAIL_CPU_STAGE_NORMAL_FINALIZED，子进程exit0、管理器自然exit1；失败不被改写为计算通过或普通exit0。

实际验证：`logs/cpu_close_pc_04.json` exit0，26项全部通过。含2项真实source-04 PC模型路径：空闲快照后的合作关闭、生成首token后取消并清除私有/工作状态，公共中性快照保留；硬件许可/加载/提交均为0，迟到输出不可交付。另以真实Linux子进程、socket、双flock和归档目录验证超时/坏退出/设备描述符/身份/租约变化、内核/GDM/扫描失败、完整扫描恢复、终结票据边界、PL阶段排除和关闭期间隔离竞态。派生异常处理入口在PC子进程内实际exit1并保留失败result与归档。所有板端设备、内核、默认平台和GDM观察均为明确PC夹具；保留owner的断言发生于测试清理前，不能作为真实板端释放证明。

失败保留：首次16项测试被DrvFS缺少原生FLOCK证据阻断，未启动模型；改用WSL原生工作区，没有放宽owner检查。第二次14/16通过，修复关闭后读取已关闭journal和测试夹具等待预期；之后revision02的25项通过，最后revision03增加关闭中quarantine复核并完整26项通过。原失败回执、各版源码和全部PC子进程原始日志都保留。

保留性：{len(baseline['protected'])}个原文件长度/SHA256不变，旧source-03/04、旧板包、原BOARD失败/现场回执与source-04既有通过摘要保持。没有重做source-03。测试import曾在旧包新增15个.pyc缓存，已单独复制并校验归档；自动审批拒绝清理命令（blocked by policy，未给更具体原因），删除未执行，15个缓存仍在原位。原源码、manifest和原始证据未变；后续测试显式禁写字节码。此附加文件事实不被写成“原包完整文件清单从未变化”。

本次仅Python控制器修订，无需重做已通过A53模型构建。没有生成可部署新板包、冻结新window/预算或运行旧恢复脚本。现有板端管理器未更新，原隔离现场没有因此自动恢复；当前boot/PID/租约均未重查。先等待用户另行授权恢复；之后按真实现场审核恢复并证明释放/默认平台恢复，再准备独立新板测窗口和版本pin。实际CPU故障闭环、PL数值/消费、CMA/TTFT与完整退出仍须实板验证；V07/V08与教师审核问题仍保留。BOARD=NOT_TESTED，新增PL=0，实板TTFT=null，≤10秒目标未验收，A12第11步PENDING。

机器汇总：SUMMARY_PC.json；最终源码：manager-source-03/；原始测试：pc-run-04/files/；测试索引：TEST_NAME_INDEX_FINAL.md；模型协作记录：DEEPSEEK_FORMATTING_RECEIPT.json。此报告不是TT10-01整体完成封存。
'''
    with (base/'REPORT_PC.md').open('x',encoding='utf-8',newline='\n') as f:f.write(report)
    shared=['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','design/qwen35/A12_TT10_01_PREFIX_STATE.md']
    before={name:(ROOT/name).read_bytes() for name in shared}
    for name,raw in before.items():
        path=base/'shared-before-closeout'/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(raw)
    relative=base.relative_to(ROOT).as_posix();handoff='docs/handoffs/A12_TT10_01_CPU_CLOSE_PC_20261025.md'
    note=f'''## 2026-10-25 TT10-01 CPU关闭通道PC通过，未部署且不恢复板端

独立管理器源码修订{relative}/manager-source-03完成CPU登记、合作关闭、正常退出后新鲜关闭检查，计算锁存不解除，原完整扫描/默认平台/GDM/归档/双锁规则保留。最终26项PC测试通过，含2项真实source-04 CPU模型关闭/取消，以及派生失败入口在PC进程内exit1、失败结果与租约归档；原失败不改为计算PASS。超时、坏退出、身份/设备/租约/内核/扫描/GDM异常与关闭时quarantine仍保留owner。原余量阈值不变，拒绝前保存准确样本。平台/GDM/内核/设备状态仅PC夹具，BOARD未测试。

原{len(baseline['protected'])}个保护文件SHA/长度不变；旧包新增15个测试字节码已归档，清理被自动审批拒绝（blocked by policy）而留在原位，原源码/manifest/证据未变。DeepSeek仅排版25个固定测试名称，主代理核验，核心实现与验收未委派；实际模型设置unknown。首次DrvFS检查及第二次测试失败保留。无SSH/板端更新/恢复/终结/租约操作，无新板包或独立窗口准备。TT10-01未完成，PL新增0、实板TTFT=null、≤10秒未验收，TT10-02未开始、A12第11步PENDING，A13条目保留。用户另行授权恢复并证明释放后才准备独立新板测窗口。报告 `{relative}/REPORT_PC.md`，接续 `{handoff}`。
'''
    for name in shared[1:6]:
        raw=before[name];nl='\r\n' if b'\r\n' in raw else '\n'
        assert (ROOT/name).read_bytes()==raw
        (ROOT/name).write_bytes((note+'\n').replace('\n',nl).encode()+raw)
    name=shared[0];raw=before[name];text=raw.decode('utf-8');data=json.loads(text)
    key='a12_ttft10_01_in_progress_20261025';entry=data[key]
    entry['status']='INCOMPLETE_CPU_CLOSE_PC_PASS_BOARD_RECOVERY_DEFERRED';entry['updated_beijing']=now
    entry['cpu_close_pc']=dict(status=summary['status'],tests=26,actual_source04_CPU_cases=2,candidate=summary['candidate_directory'],
        report=relative+'/REPORT_PC.md',summary=relative+'/SUMMARY_PC.json',deployed=False,BOARD='NOT_TESTED',new_window_prepared=False,
        compute_latch_reset=False,original_failure_manager_exit_code=1,DeepSeek_used_for='25 fixed test-name Markdown rows only',actual_model_settings='unknown',
        original_protected_files_unchanged=len(baseline['protected']),extra_parent_bytecode_files=15,cache_cleanup='REJECTED_BLOCKED_BY_POLICY_NO_DELETION')
    entry['next']=summary['next'];entry['report']=relative+'/REPORT_PC.md';entry['cpu_close_handoff']=handoff
    start=text.index('{',text.index(json.dumps(key)));_,length=json.JSONDecoder().raw_decode(text[start:]);end=start+length
    nl='\r\n' if '\r\n' in text else '\n';replacement=json.dumps(entry,ensure_ascii=False,indent=2).replace('\n','\n  ').replace('\n',nl)
    updated=text[:start]+replacement+text[end:];parsed=json.loads(updated)
    assert {k:v for k,v in parsed.items() if k!=key}=={k:v for k,v in data.items() if k!=key}
    assert (ROOT/name).read_bytes()==raw;(ROOT/name).write_bytes(updated.encode())
    name=shared[-1];raw=before[name]
    old='CPU故障正常终结/新鲜关闭检查仍待实现'.encode();new='CPU故障正常终结/新鲜关闭检查已在独立源码通过26项PC验证，尚未部署，板端旧管理器未改变'.encode()
    assert raw.count(old)==1 and (ROOT/name).read_bytes()==raw
    (ROOT/name).write_bytes(raw.replace(old,new,1))
    with (ROOT/handoff).open('x',encoding='utf-8',newline='\n') as f:
        f.write('# TT10-01 CPU关闭通道无板交接\n\n'+note+'\n旧交接与source-04报告保留。下一次先读PROJECT_STATUS、本交接、CPU关闭报告和原跨对话交接中的现场/恢复边界。现有板端代码尚无此通道，不能直接用旧PID、旧恢复脚本或此PC修订自动操作现场。任何独立板测窗口须在另行授权恢复、重新核实身份及证明释放之后准备。\n')
    save(base/'SHARED_CLOSEOUT.json',dict(status='PASS',before={name:hashlib.sha256(raw).hexdigest() for name,raw in before.items()},after={name:sha(ROOT/name) for name in shared},
        other_project_status_entries_unchanged=True,history_text_retained=True,handoff=dict(path=handoff,sha256=sha(ROOT/handoff))))
    print(json.dumps(dict(status=summary['status'],tests=26,report=str(base/'REPORT_PC.md'),task01_complete=False,BOARD='NOT_TESTED')))


if __name__=='__main__':main()
