"""Record the exact offline scope; leave live Board issuer and PL mode open."""
import json
from pathlib import Path
import subprocess
import sys
from generation_evidence import ROOT,OUT,PARENT,DOCS,read,save,sha,pin
KEY='a12_generation_consumer_offline_20261026'
HANDOFF='docs/handoffs/A_A12_GENERATION_CONSUMER_OFFLINE_20261026.md'

def main():
    before=read(OUT/'PROJECT_STATUS.json.before');assert KEY not in before
    for n in DOCS:assert (ROOT/'docs'/n).read_bytes()==(OUT/(n+'.before')).read_bytes(),n
    review=read(OUT/'ARTIFACT_REVIEW.json');assert review['status']=='PASS_PC_NATIVE_GENERATION_CONSUMER_AND_A53_COMPILE_ONLY'
    package=read(OUT/'PACKAGE_REVIEW.json');assert sha(ROOT/package['archive']['path'])==package['archive']['sha256']
    for row in read(OUT/'BASELINE.json')['files']:assert sha(ROOT/row['path'])==row['sha256']
    older=read(PARENT/'PRESERVATION.json')['old_source_pins']+read(PARENT/'FINAL_REVIEW.json')['source']
    for row in older:assert sha(ROOT/row['path'])==row['sha256']
    probe=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1';baseline=read(probe/'BASELINE.json')
    for row in baseline['parent_files']:assert sha(Path(baseline['parent_bundle'])/row['path'])==row['sha256']
    for row in baseline['contract_files']:assert sha(row['path'])==row['sha256']
    assert sha(probe/'bundle-v2.zip')=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    for label,script in [('HISTORICAL_CONTRACT_GUARD','scripts/release/check_contracts.py'),('QWEN35_CONFIG_GUARD','scripts/release/qwen35_config.py')]:
        cmd=[sys.executable,script];r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        save(OUT/(label+'.json'),dict(command=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));assert r.returncode==0
    artifacts=review['runtime_artifacts']+[review['generation_writer'],review['ARM_artifact']]
    cmd=['wsl','-d','KV260-A-2204','--','sha256sum','--']+[row['path'] for row in artifacts]
    result=subprocess.run(cmd,capture_output=True,text=True)
    save(OUT/'ARTIFACT_HASH_CHECK.json',dict(command=cmd,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
    assert result.returncode==0 and [line.split()[0] for line in result.stdout.splitlines()]==[row['sha256'] for row in artifacts]
    save(OUT/'DEVELOPMENT_FAILURES.json',dict(status='FAILURES_RETAINED_NO_TARGET_WAIVER',failures=[
        dict(record='CPU_ADAPTER-v1.json',exit_code=1,cause='Missing frozen prefix_cache.hpp include dependency',fix='Copy all pinned original headers, no installation; v2/v3 compile succeeded'),
        dict(record='IMPORT_FAILURE-v1.json',exit_code=1,cause='Dedented AST hook continuation indentation',fix='Use dedented indentation; import and actual windows subsequently ran'),
        dict(record='model01-cap72/RESULT.json',exit_code=1,cause='Journal epoch is reserved; duplicate keyword rejected at bootstrap, claims0',fix='Use generation_epoch; retain DIRTY/failed window, no compute result accepted'),
        dict(record='model02-bad-copy/RESULT.json',exit_code=1,cause='Expected-fault evaluator was called before last_native_message was attached; false negative despite correct target',
            fix='Attach actual packet before exact evaluation; final graph-copy fault rerun passed with claims1/CPU1/copy0 and exact error'),
    ],development_windows_not_final_acceptance=['model01','model02'],earlier_PC_builds_and_model03_retained=True))
    remaining=[
        dict(id='LIVE_DEVICE_GENERATION',BOARD_required=False,work='Wire the independent issuer to the original already-owned platform/lease/dual-lock, live boot/driver/kernel and native BO-inventory gates; cover all platform mutation paths with revoke-before-mutation and original release interlock. PC fixture issuer must never become Board authority.'),
        dict(id='PL_MODE',BOARD_required=False,work='Bind the actual model/private generation consumer to the PL mode coordinator, unknown-inflight retention and explicit new-window strict fallback; retain bounded 3-request acceptance scope.'),
        dict(id='BOARD',BOARD_required=True,work='Only after fault recovery, confirmed safe release, fresh original gates and separate compute authorization, run the unchanged ordinary resource probe first.')]
    save(OUT/'NEXT_WORK.json',dict(goal_status='active',remaining=remaining,automatic_Board_action=False))
    activation=dict(BOARD='NOT_TESTED',ARM_execution='NOT_EXECUTED',board_operations=0,Board_generation_issuer='NOT_IMPLEMENTED_DISABLED',
        PC_generation_consumer='IMPLEMENTED_ACTUAL_MODEL_TESTED',ARM_generation_consumer='COMPILED_BOARD_DOMAIN_ONLY',
        device_open='HARD_DISABLED_BEFORE_DEVICE_OPEN',private_begin_end_ARM='UNSUPPORTED',production_enabled=False,
        ordinary_probe_replaced=False,actual_PL_results_consumed=False,release_authority=False,replay_allowed=False,
        Board_CMA=None,Board_latency_saving_s=None,PL_mode_coordinator='NOT_IMPLEMENTED',SERVICE_ready=False)
    save(OUT/'ACTIVATION.json',activation)
    completion=read(PARENT/'COMPLETION_AUDIT.json')
    completion.update(previous_turn_classification='progress',current_turn_classification='progress',whole_goal_achieved=False,goal_status='active',next_safe_action=remaining[0]['work'])
    completion['requirements'].append(dict(id='GENERATION_CONSUMER',offline='21_LINUX_ISSUER_TESTS_22_NATIVE_ASSERTIONS_NORMAL_AND_ASAN_UBSAN_SIX_ACTUAL_MODEL_WINDOWS',
        ARM='COMPILE_ONLY_BOARD_DOMAIN_PC_CREDENTIAL_REFUSED',live_Board_issuer='NOT_IMPLEMENTED',BOARD='NOT_TESTED',evidence=HANDOFF))
    save(OUT/'COMPLETION_AUDIT.json',completion)
    report=f'''# A12 代次批准消费：无板进展（2026-10-26）

本轮完成**原生代次消费门槛及其PC真实模型验证**：21项Linux实际FD/flock/租约测试、22项原生断言（普通及ASan/UBSan各一轮）、6个实际Qwen窗口（严格/微批正常及4个指定故障）通过；独立审计读取实际stdout、私有原件、日志链及冻结普通基线。A53 XRT派生库编译通过，未执行。

**仍未完成真实设备代次批准来源和PL模式协调器。当前只有PC隔离夹具可签发一次性能力；Board签发工厂硬拒绝，ARM在device_open前仍返回UNSUPPORTED。不能把本轮称为设备安全验收通过、普通包已可上板、无限请求SERVICE就绪或无板工作全部完成。**

## 实现及与时延目标的关系

沿用上一轮实际Qwen前端、Route和原数学DSO/量化对象；仅将CPU适配器/派生XRT后端的私有Control替换成代次检查包装。两个派生均做唯一锚点修改并逆向还原SHA核对，公共契约及原SP_LINEAR_V1/私有协议导出符号保持。原普通R0/warm/hit、短提示词失败和长前缀/CMA失败记录保留。

原4096字节sealed memfd中，在原Page128字节和请求Extra64字节之后增加192字节Slot，合计使用384字节；不新增CMA BO。每次权重加载、请求绑定、传输、启动、完成及维护仍执行旧门槛，同时就地检查代次域、随机epoch、实际context摘要、阶段、撤销和健康有效期；可能阻塞的旧授权交换及原start-intent之后再次检查。调用热路径不读租约文件、不逐投影登记新日志，不增加长前缀诊断或原件扫描。

租约/双锁较慢检查由管理端执行：保留实际pidfd/起始ticks/boot、两把实际FLOCK及规范路径/inode/权限、两个上限16KiB的文件读取器。批准是持有issuer对象的单次能力，JSON/复制对象/错context/过期/重放都不能消费。正常READY之后才固化真实CPU常驻状态摘要；没有伪造BO或硬件meta。周期检查及请求边界检查失败，先原子撤销，再处理日志/关闭通信；保留失败FD/DIRTY和未知在途，不自动释放或重试。平台变更接口只执行撤销并拒绝，未执行任何变更。

PC域1与Board域2由编译类型固定；PC正向签发库只签域1，ARM消费者要求域2。测试用失效注入只在x86 PC宏下存在，A53二进制不含该环境变量字符串。这仍是可信协作进程的故障协议，不隔离恶意原生代码或root。将来所有实际PL/驱动重配路径必须接撤销和原释放互锁；仅比对相同UUID或一张JSON不能证明期间未重配。

## 实际验证范围

最终6窗口为cap72、cap1正常，代次来源变化、Slot单独过期、BEGIN fsync失败、图拷贝破坏。正常均1440/648/792次真实CPU调用，合计2880次；40或2880条计算grant，与原请求/预算一致。输出token/文本/自然EOS/末位置logits、清理状态及warm运行时快照摘要匹配冻结普通CPU基线；未新增全层/全位置中间值审计，不代表真实PL数值通过。

代次来源变化在第5次claim前后确定触发：CPU实际启动/完成各4次、图拷贝4次、claims5，0个可交付结果，unknown保留。Slot单独过期场景中，旧Gate已经提交第5次start-intent，新原生代次检查仍在实际CPU计算前拒绝：实际CPU仍4次，START/unknown保留。该场景证明新增消费门槛确实参与执行。两者均CPU进程合作exit2、同一持有pidfd确认终止；这不是板端资源释放证据。

BEGIN完整记录fsync失败仍不进入计算；图拷贝破坏以claims1/CPU1/copy0和精确`private graph copy differs`错误拒绝。不得用任意提前错误替代指定目标。独立审计同时核对新增GENERATION_BIND/RESIDENT的顺序、域/摘要，原日志链/回执/交付fence及当前私有原件镜像。

开发失败完整保留，见DEVELOPMENT_FAILURES.json：首次缺头文件、AST缩进、日志保留字段冲突，以及故障评估包未及时附带造成的假阴性。最终目标未放宽。补上私有目录权限新检查后，21项夹具及最终6整窗再次执行。没有安装、重装或升级依赖。

本轮没有新增可用于板端预测的时延数据。新增门槛通过共享页就地执行，较慢检查留在管理端，服务于“输入后尽快得到经过门槛的应答”；真实TTFT/端到端收益及CMA余量仍为null，不能套用上一轮PC秒数。

## 制品与后续

审阅包：`{package['archive']['path']}`，SHA `{package['archive']['sha256']}`。逐成员CRC/SHA回读通过；依赖冻结仓库和原运行时/模型，不是部署包。无GGUF/sidecar/bitstream/安装恢复或上板执行脚本。

原普通包仍为未来首轮板端资源探测基线，SHA `acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`。CmaFree≥98304KiB、MemAvailable≥1114112KiB、原核日志/温度/租约/双锁/BO/未知在途门槛均未更改。

下一步无板接原有Owner/Platform的真实批准来源和BO校验、覆盖平台变更互锁，再接PL模式协调器。本轮不上板、不连接SSH、不恢复/卸载/释放、不推送仓库。实际模型设置不可核实，记unknown；核心设计/验收未委派DeepSeek。
'''
    with (ROOT/HANDOFF).open('x',encoding='utf-8') as f:f.write(report)
    summary='A12代次消费门槛已完成PC实际模型验证：21 Linux夹具、22原生断言及sanitizer、6指定整窗和A53编译通过。共享4096页使用384字节，不加CMA BO/长前缀诊断。实际Board批准来源与PL模式仍未完成，ARM入口禁用，普通包/门槛/失败记录保留、目标active。'
    status=dict(before);status[KEY]=dict(status='PC_CONSUMER_VALIDATED_A53_COMPILED_LIVE_BOARD_ISSUER_UNBOUND',evidence=HANDOFF,
        actual_model_windows=6,issuer_tests=21,native_assertions=22,goal_status='active',whole_goal_achieved=False,**activation)
    (ROOT/'docs/PROJECT_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in DOCS[1:]:
        with (ROOT/'docs'/name).open('a',encoding='utf-8') as f:f.write('\n\n## A12代次消费门槛无板进展（2026-10-26）\n\n'+summary+' 见 `'+HANDOFF+'`。\n')
    final=read(ROOT/'docs/PROJECT_STATUS.json');assert {k:v for k,v in final.items() if k!=KEY}==before
    for name in DOCS[1:]:assert (ROOT/'docs'/name).read_bytes().startswith((OUT/(name+'.before')).read_bytes())
    save(OUT/'PRESERVATION.json',dict(status='PASS',parent_source_evidence_files=len(read(OUT/'BASELINE.json')['files']),old_source_pins=older,
        original_parent_files=len(baseline['parent_files']),contracts=len(baseline['contract_files']),other_status_entries_exact=len(before),
        original_probe_SHA256=sha(probe/'bundle-v2.zip'),governance_text_preserved_as_prefix=True,board_contacted=False,pushed=False))
    sources=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').iterdir()) if p.is_file() and p.name.startswith(('generation_','test_generation_'))]
    evidence=[pin(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('FINAL_REVIEW.json','TERMINAL_VERIFICATION.json')]
    governance=[pin(ROOT/'docs'/name) for name in DOCS]+[pin(ROOT/HANDOFF)]
    save(OUT/'FINAL_REVIEW.json',dict(status='PASS_PC_GENERATION_CONSUMER_OFFLINE_SCOPE_ONLY',source=sources,evidence=evidence,governance=governance,
        BOARD='NOT_TESTED',live_Board_issuer='NOT_IMPLEMENTED',whole_goal_achieved=False,goal_status='active'))
    count=0
    for row in sources+evidence+governance:
        p=ROOT/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'];count+=1
    save(OUT/'TERMINAL_VERIFICATION.json',dict(status='PASS_ALL_LISTED_CURRENT_BYTES',pins_verified=count,
        final_review_SHA256=sha(OUT/'FINAL_REVIEW.json'),whole_goal_achieved=False,goal_status='active',BOARD='NOT_TESTED'))
    print('PASS_ALL_LISTED_CURRENT_BYTES',count)
if __name__=='__main__':main()
