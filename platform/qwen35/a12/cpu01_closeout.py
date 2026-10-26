"""Record task 01 only after BOARD audit; preserve concurrent A13 status entries."""
import datetime
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'
REL=OUT.relative_to(ROOT).as_posix()


def j(p):return json.loads(p.read_text(encoding='utf-8'))
def pin(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as stream:stream.write(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def edit(name, transform):
    p=ROOT/name;before=p.read_bytes();after=transform(before.decode('utf-8')).encode('utf-8')
    save(OUT/'before-docs'/name,before.decode('utf-8'))
    assert p.read_bytes()==before,'Concurrent document changed'
    temp=p.with_name(p.name+'.cpu01.tmp')
    with temp.open('xb') as stream:stream.write(after);stream.flush();os.fsync(stream.fileno())
    assert p.read_bytes()==before,'Concurrent document changed; temporary retained'
    os.replace(temp,p);save(OUT/'after-docs'/name,after.decode('utf-8'))


def main():
    for name in ('contracts_final.json','config_final.json','analyze_01.json','integrity_01.json','pc_model_01.json','python_failure_01.json','build_03.json','reader_01.json'):
        assert j(OUT/'logs'/name)['exit_code']==0,name
    assert j(OUT/'deployment_01/receipt.json')['exit_code']==0
    assert j(OUT/'deployment_01/stdout.txt')['deployment']['fresh_no_users_gate']
    audit=j(OUT/'BOARD_AUDIT.json');assert audit['task01_complete'] and audit['actual_PL_calls']==7632
    package=j(OUT/'PACKAGE.json');account=j(OUT/'ACCOUNTING.json');hot=j(OUT/'HOTSPOTS.json');over=j(OUT/'OBSERVER_OVERHEAD.json')
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    categories='\n'.join('| '+r['category']+' | '+f"{r['wall_ms']/1000:.6f}"+' | '+str(r['timed_groups'])+' |' for r in hot['phases']['prefill']['exclusive_categories'])
    mg=hot['phases']['prefill']['management'];exclusive=mg['manager_exclusive_ms']
    manager='\n'.join('| '+k+' | '+f'{v/1000:.6f}'+' |' for k,v in exclusive.items())
    timing='\n'.join('| '+r['mode']+'/'+r['side']+'/'+r['input']+' | '+f"{r['plain_complete_s']:.3f}"+' | '+f"{r['profile_complete_s']:.3f}"+' | '+f"{100*r['profile_over_plain_fraction']:+.2f}%"+' |' for r in over['rows'])
    report=f'''# CPU任务01：01A＋01B兼容集成与板上更新

日期：{now}。维护者A，节点分类来源B。状态 **PASS_BOARD_CPU01_COMPATIBLE_AND_UPDATED，CPU计划01完成**。

修复了01A对当前共享输出头 `token_embd.weight` 的漏识别；仅在MUL_MAT、1024×248320、Q6_K及结构匹配时归为output_head，GET_ROWS仍为数据移动。独立保留原01A回交及失败反例。新增显式旧格式/V2读取器，验证父级与节点记账有效性、类别/角色视图守恒和融合计数，与原01B实际顺序/原生阶段计数关联组合。

## 实施与验证

- 仅模型观察源码request_profile.cpp/hpp改变，主程序/bridge/route数学源码、GGML/CPU/PL库、位流、稳定投影03、公共契约及fixtures保持不变。
- Linux组件：157分类断言、60真实图/1308断言、实际60融合附加节点、ELF入口及9项共享输出头回归通过。原peer review的6旧刻画/126投影回归继续保留，未冒充本次重跑。
- Linux真实模型：旧版与新版剖面关/开各443个二进制文件（216投影X/Y、10 logits、prefill混合状态）逐位相同；decode结束的完整状态fingerprint相同，4类错误读取输入被拒绝。
- 01B原13项socket/日志/所有权/健康/fsync/过期与重放失败测试重新通过；组合管理器所有权、健康、接收、BO校验及恢复函数AST未变，安全模块字节未变。
- 2026.1 SDK、Cortex-A53交叉构建通过，禁止native/fast-math/重结合；沿用原有全部运行库，交叉构建不是BOARD证据。
- BOARD两个顺序新窗口，每窗口CPU及PL两模式、先9-token完整数值诊断再短普通/剖面及107-token自然普通/剖面，共7632次真实PL调用。旧S1/旧S2、新S1/新S2、旧/新同后端全部443份二进制文件逐位相同，递归/卷积/KV混合状态及最终fingerprint相同。所有普通/剖面自然生成文本、EOS、token及最后prompt logits摘要一致。
- 每窗口72权重只加载一次、148 BO、140591104字节预算；每次PL submit都有独立新鲜健康及持久许可，全部退出码0。独立及延迟后验均恢复默认PL/GDM、无ZOCL、无active租约、双锁无人持有。

## 同一prefill的互斥节点类别

来自组合版BOARD S2/natural_profile。融合组时间归首节点；角色/shape聚合是同一时间的另一视图，不能重复相加，也不能将CONCAT等时间归为纯矩阵运算。unknown显式保留。

| 类别 | 秒 | 实测组数 |
|---|---:|---:|
{categories}

元数据准备 {hot['phases']['prefill']['metadata_prepare_s']:.6f} 秒，释放 {hot['phases']['prefill']['metadata_release_s']:.6f} 秒。自然样本detail=false按role/type/shape/层族合并层号及weight名；diag_exact的detail=true保留完整层号/权重身份。节点组时间与图墙时余额含既有计划、屏障/调度及计时粒度，不是纯锁等待。所有嵌套关系及prefill/decode均见ACCOUNTING.json。

## 同一prefill的管理许可分项

原生许可等待 {mg['native_permission_wait_ms']/1000:.6f} 秒；管理端实际wall {mg['manager_wall_ms']/1000:.6f} 秒、管理线程CPU {mg['manager_thread_cpu_ms']/1000:.6f} 秒；两者余额 {mg['channel_client_scheduling_remainder_ms']/1000:.6f} 秒包含通道、客户端、调度和边界，不能称纯IPC。

| 管理端互斥分项 | 秒 |
|---|---:|
{manager}

JSON编码、write/flush/fsync、健康kernel读取/校验/归档与owner子项为嵌套视图，详见HOTSPOTS.json，不能与上表父项相加。普通模式原生phase计数未开启，许可保持UNATTRIBUTED，不按调用数均摊。

原01B raw收集器按同名request id取行，S2文件会保留先前S1的idle行；本组合审计按每次实际client时钟范围过滤idle并单列排除数，不把旧idle或idle总量加入PL许可阶段。prefill/decode提交的计数与时间均在当前请求边界内，未受影响。

## 观察扰动及限制

| 版本/后端/输入 | 普通完整秒 | 剖面完整秒 | 相对差 |
|---|---:|---:|---:|
{timing}

每格只有1个实测样本，固定旧后新顺序、文件cache不保证冷；管理观察器两版均开启。以上是诊断扰动描述，不能作优化收益、统计显著或p95结论。普通模式不建立节点metadata；剖面模式不得用于报告正常速度。已记录worker进程CPU、主线程上下文切换及管理进程/线程CPU；无设备周期/功耗，值为null。库内部融合状态更新不可独立计时，值保持null。

任务01已足以定位下一步：02持久许可记录/fsync及健康路径重复JSON优先；非MLP CPU的matrix类别约12.754秒，05线性注意力投影值得后续独立评估。03仍等待队友独立结果，整个data_movement类别约1.388秒不能直接称可消除时间。NEXT_STEPS.json记录据实测修订的后续优先级，并保留最初自动建议。本次未实施02/03/05性能优化，也不标CPU整体优化、A12第11步或A13完成。

## 板上版本与回退

已部署并实际运行：`/var/lib/kv260-a12/cpu01-integrated-20261024-v1`。主程序SHA256 `{package['configurations'][1]['program_sha256']}`。保留完整包manifest/source、实际运行日志和独立回读。

原健康基线`/var/lib/kv260-a12/health-opt-20261024-v1`及本次旧对照`/var/lib/kv260-a12/cpu01-old-20261024-v1`均保留，未覆盖原库/位流或启用默认FPGA。后续用新维护窗口从所选包派生，不能重放本次已用review/lease或直接重跑已消耗的run-v1。正常恢复已经完成；未知DMA状态仍禁止强杀/卸载。见ROLLBACK.md。

原失败与修复在FAILURES.json；原01A包、00、01B和旧健康封存共2389文件hash保持不变。PC/CROSS_BUILD/BOARD已测；Csim/Cosim/综合/实现本次未做。实际助手模型/推理设置unknown，无子代理，无远程push。
'''
    save(OUT/'REPORT.md',report)
    save(OUT/'ROLLBACK.md',f'''# 01板上更新与回退

组合候选：/var/lib/kv260-a12/cpu01-integrated-20261024-v1，程序SHA {package['configurations'][1]['program_sha256']}。
旧健康基线：/var/lib/kv260-a12/health-opt-20261024-v1，旧程序SHA b32697e27b5e8bdb839df8038c88ef00a23e3325aa558272bc6bf2538c9d2cdd。
本次旧同板对照：/var/lib/kv260-a12/cpu01-old-20261024-v1。

各包独立完整保存，当前默认PL/GDM已恢复；系统默认后端未改变。下次使用任一版本均须新身份/boot/kernel/FD/VMA/资源/双锁门禁，派生新窗口ID、review、lease、manifest及run目录，再按同一正常关闭/恢复路径运行。不能重放本次控制授权，也不能在有owner/未知DMA时直接切换、强杀、卸载或删锁。

关闭请求profile可关01A热路径观察；01B源模块保留原控制版cpu01b_control_manager.py，需在新的审查包中选择，不能修改已封存运行包。观察器与安全逻辑独立，关闭观察不关闭新鲜检查、持久确认或失败闭锁。
''')
    failures=[]
    for p in sorted((OUT/'logs').glob('*.json')):
        log=j(p)
        if log.get('exit_code') not in (None,0):failures.append(dict(log=p.relative_to(OUT).as_posix(),exit_code=log['exit_code'],elapsed_s=log.get('elapsed_s'),stderr=log.get('stderr')))
    save(OUT/'FAILURES.json',dict(failures=failures,retained_peer_failure='../20261024-cpu-peer01a-review-v1/logs/tied_head_repro_01.json',repair_notes=['build01: versioned libcrypto.so.3 fallback, reuse installed runtime; no install','build02: correct pinned vendor/nlohmann include','package01: Windows UTF-8 explicit read; no board started by failed package'],board_failures=0))
    save(OUT/'PROFILE_SCHEMA.json',dict(parent='N02_REQUEST_PROFILE_V1',legacy_node='NO_SCHEMA_EXACT_SEVEN_BUCKET_SIGNATURE',node='A12_CPU_NODE_PROFILE_V2',management='A12_CPU01B_MANAGEMENT_V1',reader='platform/qwen35/a12/cpu01_profile.py',semantics='exclusive head-op categories; fused members separately counted, child elapsed null; role/shape alternate nonadditive view; management nested below native permission wait; plain native phase unavailable',runtime_BOARD_placeholders='Inherited generic profiler fields are NOT_TESTED literals; authoritative physical domain is validated outer BOARD_AUDIT and pinned worker identity, not these source placeholders.'))
    save(OUT/'RESULTS.json',dict(status=audit['status'],task01='COMPLETE',PC='PASS',CROSS_BUILD='PASS',BOARD='PASS',CSIM='NOT_TESTED',COSIM='NOT_TESTED',SYNTHESIS='NOT_TESTED',IMPLEMENTATION='NOT_TESTED',diagnostic_overhead='MEASURED_SINGLE_SAMPLE_ONLY',actual_PL_calls=7632,default_FPGA_enabled=False,A12_step11='PENDING',task02='NOT_IMPLEMENTED',task03='NOT_CHANGED',report=REL+'/REPORT.md'))
    def status(text):
        data=json.loads(text)
        new=dict(status=audit['status'],updated_beijing=now,task01='COMPLETE',original_peer='PRESERVED_READ_ONLY',peer_R1='FIXED_IN_A_DERIVED_VERSION',compatibility='V1_V2_AND_01B_PASS',PC='PASS_BIT_EXACT',CROSS_BUILD='PASS_2026_1_A53',BOARD='PASS_BIT_EXACT_AND_NORMAL_RESTORE',real_PL_calls=7632,diagnostic_overhead='SINGLE_SAMPLE_MEASURED_NO_LOW_PERTURBATION_CLAIM',board_candidate=audit['board_candidate'],rollback=audit['rollback'],report=REL+'/REPORT.md',task02='NOT_IMPLEMENTED',task03='NOT_CHANGED',default_FPGA_enabled=False,A12_step11='PENDING',actual_model_settings='unknown',subagents=0)
        assert 'a12_cpu01_integrated_20261024' not in data
        return json.dumps(dict(a12_cpu01_integrated_20261024=new,**data),ensure_ascii=False,indent=2)+'\n'
    edit('docs/PROJECT_STATUS.json',status)
    entry=f'\n## 2026-10-24 CPU01兼容与板上更新\n\n01A共享输出头缺口在A独立派生版修复，旧格式/V2读取器与01B兼容，PC/A53/BOARD通过，CPU计划01完成。两个新窗口7632真实PL调用；旧/新同板全部投影、logits及混合状态逐位相同，正常关闭并独立/延迟恢复通过。候选部署于`/var/lib/kv260-a12/cpu01-integrated-20261024-v1`，原基线与失败保留；扰动仅单样本描述，不宣称低扰动/加速，02/03未实施，默认FPGA不变，第11步PENDING。报告 `{REL}/REPORT.md`。实际模型设置unknown，无子代理。\n'
    for name in ('docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md'):
        edit(name,lambda text:entry+'\n'+text)
    def plan(text):
        head='### 01｜补足最小诊断，先回答时间花在哪里';start=text.index(head);end=text.index('### 02｜',start)
        block=text[start:end].replace('- [ ]','- [x]')
        block+=f'**2026-10-24最新执行：01完成。** 01A修订和01B兼容，实际PC/A53/BOARD及正常恢复通过；扰动只作单样本描述，见[组合报告](../{REL}/REPORT.md)。02/03未实施，A12第11步PENDING。\n\n'
        text=text[:start]+block+text[end:]
        text=text.replace('00本地基线冻结完成；01—09尚未完成，性能候选尚未实施','00本地基线冻结、01诊断兼容与板上更新完成；02—09尚未完成')
        return text
    edit('docs/A12_CPU_OPTIMIZATION_PLAN_20261024.md',plan)
    save(ROOT/'docs/handoffs/A_A12_CPU01_INTEGRATED_20261024.md','# CPU01兼容集成交接\n'+entry+'\n后续02优先使用HOTSPOTS/ACCOUNTING中的持久许可与健康分项；03仍由队友交付。不得把节点角色与类别或管理嵌套父子时间重复相加，不得重放已消耗窗口。\n')
    logs={p.name:j(p) for p in sorted((OUT/'logs').glob('*.json'))}
    save(OUT/'COMMANDS.json',dict(logs={k:dict(argv=v.get('argv'),exit_code=v.get('exit_code'),sha256=pin(OUT/'logs'/k)) for k,v in logs.items()},SSH='preflight_01/reservation.json and receipt; UPLOAD.json/UPLOAD_RECEIPT; board_01/reservation.json and receipt; hidden credentials never logged'))
    print('CPU01_COMPLETE_DOCUMENTED_WITH_CONCURRENT_STATUS_PRESERVED')


if __name__=='__main__':main()
