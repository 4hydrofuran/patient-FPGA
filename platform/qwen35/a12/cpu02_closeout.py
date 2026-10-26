"""Document CPU02 after real board safety/performance; preserve unrelated status."""
import datetime
import hashlib
import json
import os
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'
REL=OUT.relative_to(ROOT).as_posix()


def j(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as stream:stream.write(x if isinstance(x,str) else json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def edit(name,fn):
    p=ROOT/name;before=p.read_bytes();after=fn(before.decode('utf-8')).encode('utf-8')
    save(OUT/'before-docs'/name,before.decode('utf-8'));temp=p.with_name(p.name+'.cpu02.tmp')
    with temp.open('xb') as stream:stream.write(after);stream.flush();os.fsync(stream.fileno())
    assert p.read_bytes()==before,'Concurrent document changed; temporary preserved'
    os.replace(temp,p);save(OUT/'after-docs'/name,after.decode('utf-8'))


def main():
    for name in ('contracts_final.json','config_final.json','pc_02.json','integrity_01.json','analyze_01.json'):
        assert j(OUT/'logs'/name)['exit_code']==0,name
    audit=j(OUT/'BOARD_AUDIT.json');perf=j(OUT/'PERFORMANCE.json');assert audit['actual_PL_calls']==9792
    accepted=perf['accepted'];now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    if accepted:
        assert j(OUT/'deployment_01/receipt.json')['exit_code']==0
        assert j(OUT/'deployment_01/stdout.txt')['deployment']['fresh_no_users_gate']
    decision='ACCEPTED_BOUNDED_SAMPLE_CPU02' if accepted else 'REJECTED_CPU02_PERFORMANCE_KEEP_CPU01'
    rows='\n'.join('| '+r['side']+'/'+r['id']+' | '+f"{r['baseline']['client_first_token_s']:.3f}"+' | '+f"{r['candidate']['client_first_token_s']:.3f}"+' | '+f"{r['baseline']['client_complete_s']:.3f}"+' | '+f"{r['candidate']['client_complete_s']:.3f}"+' | '+f"{100*r['complete_fraction']:+.2f}%"+' |' for r in perf['comparisons'])
    management='\n'.join('| '+phase+'/'+key+' | '+f"{data['baseline']['manager_exclusive_ms'][key]/1000:.6f}"+' | '+f"{data['candidate']['manager_exclusive_ms'][key]/1000:.6f}"+' |' for phase,data in perf['management'].items() for key in ('owner.total','health.total','record.total'))
    waits='\n'.join('| '+phase+' | '+f"{v['baseline']['native_permission_wait_ms']/1000:.6f}"+' | '+f"{v['candidate']['native_permission_wait_ms']/1000:.6f}"+' | '+f"{100*v['native_wait_fraction']:+.2f}%"+' |' for phase,v in perf['management'].items())
    report=f'''# CPU计划02：逐次许可管理路径优化

日期：{now}。维护者A。任务02工作与有界实板评估完成；候选决定 **{decision}**。

## 实施内容

基于封存01组合版独立派生，仅改Python管理端：

1. 用最多两个不可变str对象的UTF8字节/SHA256表示消除重复转换和摘要。每次仍从kmsg读取，仍验证序列、boot、日志连续性及新增诊断；缓存不保存健康结论。无新增日志时复用同一不可变对象，变更对象重新计算表示。
2. 对已持有的两个锁FD，每次重新读取路径inode、fstat和fdinfo的FLOCK PID/WRITE状态。租约hash仍逐次重读，去掉重复遍历所有FD；缺失、替换、解锁或FD变化均失败。
3. 许可日志沿用JSONL所有解析字段和顺序，改紧凑空白及原始append FD复用。每条先核对当前路径/inode/link/文件长度，完整处理短写，随后执行本条fsync，首次创建额外同步父目录。无Python写缓冲，flush阶段为不适用；任何不确定写入均闭锁。正常worker最后一条退出记录持久后关闭日志FD。

内核归档每次仍读文件并逐字节核对；温度、内存、boot、租约、锁、预算、单在途、单许可绑定、拒绝/取消/恢复及确认前持久化保留。IPC请求/回复编解码未发现足够收益，本候选保持原样，未做预许可、批量许可或异步确认。

所有ARM程序、GGML/CPU/PL库、模型、位流、01A节点观察源码、03稳定投影和公共support/契约字节不变，程序SHA `0ec7e8dbbe2b999fb4009a10ba616b5f3ead90729b17d069dfa1c42f4313ec9d`。Python-only无需新交叉构建，沿用已验A53产物；不将复用记作新构建PASS。

## 无板验证

- 35项Linux实际socket、日志/fsync、短写、删除/替换/截断/symlink、内核读取/丢失/警告、动态锁释放/替换、重放、过期、预算、管理器退出/worker EOF及持久化等待验证通过。
- 父级01封存3742文件全部hash不变。许可处理函数、动态回调/预算/记录先于回复/失败处理及平台恢复AST不变，修改边界见INTEGRITY.json。
- 组件基准分别5组，使用实际fsync；首组两个进程重叠执行，原记录保留且不参与判定。后续顺序测量在BENCH_*_sequential.json。PC测量不替代BOARD。
- 首次测试适配脚本将目录替换误匹配到旧函数调用，1项测试脚本错误，已保存PC.failed01和原日志，修正后35项全部通过。

## BOARD数值、安全和生命周期

两个顺序新维护窗口，以同一native版本比较01基线和02候选，各CPU/PL两模式。每窗口先9-token完整数值，再短普通、两次107-token自然普通、一次自然剖面。每窗口4896真实PL调用，小于5000预算，总9792；72权重只加载一次、148 BO/140591104字节预算不变。

同板旧/新S1、旧/新S2、各自S1/S2的443份二进制文件（216投影输入输出、10 logits、prefill混合状态）逐位相同，decode终态完整fingerprint一致。每次请求R0清理和自然文本/token/EOS/最后prompt logits摘要一致。

全部许可拥有逐次新鲜健康观察，全部manager/worker退出码0，逐次健康与内核门禁通过。正常卸载测试PL/驱动并恢复默认PL/GDM后，独立和延迟FD/VMA/锁/lease/内核后验通过；没有强杀、重启或专项恢复。

## 实测许可等待（自然剖面）

| 阶段 | 01基线秒 | 02候选秒 | 相对差 |
|---|---:|---:|---:|
{waits}

### 管理端互斥分项

| 阶段/分项 | 01基线秒 | 02候选秒 |
|---|---:|---:|
{management}

fsync仍是record.total的子项；所有父子关系、CPU时间与通道/客户端/调度余额在ACCOUNTING/PERFORMANCE中。未将余额称纯IPC或纯锁等待。同名CPU/S2请求残留idle行按实际client时钟过滤，未混入许可阶段。

本轮prefill的record.total并未降低：约8.474→8.619秒；其中fsync约7.608→8.040秒。不能把FD复用解释为已经证明降低了存储同步延迟。主要测得收益来自健康检查中的重复表示/摘要以及所有权FD扫描；记录路径仍保留同步等待，单样本波动不作因果分解。

## 普通回答与剖面对照

| 后端/样本 | 基线TTFT秒 | 候选TTFT秒 | 基线完整秒 | 候选完整秒 | 完整相对差 |
|---|---:|---:|---:|---:|---:|
{rows}

采样前已冻结DESIGN.json接受规则：数值/安全/恢复先通过，prefill/decode原生许可等待均降低，两次普通PL自然样本TTFT与完整墙时均降低，普通CPU完整墙时每对不超过5%退步。实际检查 `{json.dumps(perf['checks'],ensure_ascii=False)}`。

候选决定：**{decision}**。仅两次普通配对、一次剖面对照，固定先基线后候选，文件cache不保证冷；不宣称统计显著、p95、功耗或硬件算速改变。最终08平衡顺序及至少5重复的组合验收仍待做。fsync本身的剩余等待仍保留，不能把减少持久性当成本轮收益。

## 板端版本和回退

候选位于 `/var/lib/kv260-a12/cpu02-candidate-20261024-v1`，本轮对照位于`/var/lib/kv260-a12/cpu02-baseline-20261024-v1`。选择：{'02候选，已写板端部署回执' if accepted else '继续01，候选保留为未接受实验'}。

回退包 `/var/lib/kv260-a12/cpu01-integrated-20261024-v1`及原健康/00基线均保留。后续任何版本须派生新window/review/lease及run目录；不能重放本次窗口，也不能在未知DMA/owner尚在时直接切换、强杀或卸载。默认FPGA和系统启动未改；03未改；A12第11步PENDING；A13状态保留。

PC/BOARD已测；CROSS_BUILD为NOT_REQUIRED_UNCHANGED_A53，Csim/Cosim/综合/实现本轮未做。全部失败和原始命令见FAILURES/COMMANDS；实际助手模型/推理设置unknown，无子代理，无push。
'''
    save(OUT/'REPORT.md',report)
    save(OUT/'ROLLBACK.md',f'# CPU02回退\n\n本轮候选决定：{decision}。候选 /var/lib/kv260-a12/cpu02-candidate-20261024-v1。稳定回退 /var/lib/kv260-a12/cpu01-integrated-20261024-v1，原健康基线仍保留。\n\n窗口已正常结束并恢复默认PL/GDM；重用任一包须新鲜身份/boot/kernel/资源/锁门禁及新review/lease/run，禁止重放本次窗口。未知DMA或owner未释放时沿用原隔离/恢复流程。默认FPGA未改变。\n')
    failures=[]
    for p in sorted((OUT/'logs').glob('*.json')):
        log=j(p)
        if log.get('exit_code') not in (None,0):failures.append(dict(log=p.relative_to(OUT).as_posix(),exit_code=log['exit_code'],stderr=log.get('stderr')))
    save(OUT/'FAILURES.json',dict(failures=failures,board_failures=0,first_overlapped_PC_bench_excluded=True))
    save(OUT/'RESULTS.json',dict(status=decision,task02='COMPLETE_BOUNDED_WORK',accepted=accepted,PC='PASS_35',BOARD='PASS_NUMERIC_AND_RESTORE',CROSS_BUILD='NOT_REQUIRED_UNCHANGED_A53',
        actual_PL_calls=9792,default_FPGA_enabled=False,task03_changed=False,A12_step11='PENDING',final_task08_acceptance=False))
    entry=f'\n## 2026-10-24 CPU02管理路径优化\n\n02无板及BOARD有界工作完成，决定{decision}。35项PC故障/协议验证；两个新窗口9792真实PL调用，旧/新数值逐位一致、逐次持久许可与正常恢复通过。不可变日志表示/摘要复用、逐次锁FD直查及同schema紧凑持久日志已实现，每次fsync和新鲜安全检查保留。普通自然回答2次配对，最终08更多重复仍待做；报告 `{REL}/REPORT.md`。01A/03/数学/默认FPGA/启动未改，A12第11步PENDING，A13保留。实际模型设置unknown，无子代理。\n'
    def status(text):
        data=json.loads(text);assert 'a12_cpu02_20261024' not in data
        return json.dumps(dict(a12_cpu02_20261024=dict(status=decision,updated_beijing=now,task02='COMPLETE_BOUNDED_WORK',accepted=accepted,PC_tests=35,
            real_PL_calls=9792,BOARD='PASS_BIT_EXACT_AND_NORMAL_RESTORE',CROSS_BUILD='NOT_REQUIRED_UNCHANGED_A53',report=REL+'/REPORT.md',
            board_candidate=audit['board_candidate'],selected=audit['board_candidate'] if accepted else audit['rollback'],rollback=audit['rollback'],
            final_task08_acceptance=False,default_FPGA_enabled=False,task03_changed=False,A12_step11='PENDING',actual_model_settings='unknown',subagents=0),**data),indent=2,ensure_ascii=False)+'\n'
    edit('docs/PROJECT_STATUS.json',status)
    for name in ('docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md'):
        edit(name,lambda text:entry+'\n'+text)
    def plan(text):
        start=text.index('### 02｜');end=text.index('### 03｜',start)
        block=text[start:end].replace('- [ ]','- [x]')+f'**2026-10-24执行：02有界工作完成，{decision}。** [实测报告](../{REL}/REPORT.md)，逐次fsync/新鲜检查和回退保留；最终08更多重复未完成。\n\n'
        text=text[:start]+block+text[end:]
        text=text.replace('00本地基线冻结、01诊断兼容与板上更新完成；02—09尚未完成','00、01完成；02有界管理优化完成，03—09尚未完成')
        return text
    edit('docs/A12_CPU_OPTIMIZATION_PLAN_20261024.md',plan)
    save(ROOT/'docs/handoffs/A_A12_CPU02_20261024.md','# CPU02交接\n'+entry+'\n后续03由队友独立回交后接收；05可依据01实测投影热点评估。08须更多平衡普通模式重复，不把剖面速度或PC组件时延作为最终板速。\n')
    save(OUT/'COMMANDS.json',dict(logs={p.name:dict(argv=j(p).get('argv'),exit_code=j(p).get('exit_code'),sha256=sha(p)) for p in sorted((OUT/'logs').glob('*.json'))},SSH='preflight/UPLOAD/board/deployment reservations and receipts; hidden authentication only'))
    print(json.dumps(dict(task02='COMPLETE_BOUNDED_WORK',decision=decision)))


if __name__=='__main__':main()
