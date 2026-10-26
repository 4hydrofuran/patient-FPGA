"""Close CPU01B only after actual board audit and sequential protection checks."""
import datetime
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1'
REL=OUT.relative_to(ROOT).as_posix()


def j(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def edit(name,transform):
    path=ROOT/name;raw=path.read_bytes();after=transform(raw.decode('utf-8')).encode('utf-8')
    beforepath=OUT/'before-docs'/name;beforepath.parent.mkdir(parents=True,exist_ok=True)
    with beforepath.open('xb') as stream:stream.write(raw)
    assert path.read_bytes()==raw,'Concurrent document changed'
    temporary=path.with_name(path.name+'.cpu01b.tmp')
    with temporary.open('xb') as stream:stream.write(after);stream.flush();os.fsync(stream.fileno())
    assert path.read_bytes()==raw,'Concurrent document changed; temporary retained'
    os.replace(temporary,path)
    destination=OUT/'after-docs'/name;destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as stream:stream.write(after)


def main():
    for name in ('analyze_01.json','contracts_final.json','config_final.json'):
        assert j(OUT/'logs'/name)['exit_code']==0
    audit=j(OUT/'BOARD_AUDIT.json');assert audit['status']=='PASS_BOARD_CPU01B_BOUNDED_DIAGNOSTICS'
    account=j(OUT/'ACCOUNTING.json');prefill=account['profiles']['s2/natural_profile']['accounting']['prefill']
    decode=account['profiles']['s2/natural_profile']['accounting']['decode']
    overhead=j(OUT/'OBSERVER_OVERHEAD.json');now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    rows='\n'.join('| '+name+' | '+f'{value/1000:.6f}'+' |' for name,value in prefill['manager_exclusive_ms'].items())
    nested=prefill['nested_spans_ms']
    nestedrows='\n'.join('| '+name+' | '+f'{nested.get(name,0)/1000:.6f}'+' |' for name in (
        'record.json_encode','record.write','record.flush','record.fsync','record.file.open','record.file.close',
        'health.kmsg_drain','health.kernel_gate','health.kernel_emit','health.archive_encode','health.archive_hash','health.archive_check_or_write',
        'health.temperatures','health.meminfo','health.reserve','owner.lease_locks','owner.maps'))
    timingrows='\n'.join('| '+r['backend']+'/'+r['id']+' | '+f"{r['complete_off_s']:.6f}"+' | '+f"{r['complete_on_s']:.6f}"+' | '+f"{r['complete_fraction']*100:+.2f}%"+' |' for r in overhead['rows'])
    report=f'''# A12 CPU优化01B：Python管理路径诊断

日期：{now}。维护者A。状态 **PASS_BOARD_CPU01B_BOUNDED_DIAGNOSTICS**。

完成独立Python观察器、无板控制路径验证和两个顺序实板窗口，原健康管理器off与观察器on使用同一ARM程序、库、模型、sidecar与PL位流。节点分类01A、稳定投影03、公共契约和数学未改。01B提供分项诊断；没有实施02性能优化，没有启用默认FPGA，A12第11步PENDING。

## 验证与范围

- Linux x86_64 PC：13项实际派生处理器测试通过，含真实socket、序列/身份/重放、取消/预算/过期、所有权/健康失败、write/fsync失败无许可回复、阶段关联、请求清空与原持久记录字段比较。
- 8份Python代码去除观测包装、关联调用和局部编码变量后，与冻结原代码AST逐项相同；真实派生manager仅导入、不执行main的PC检查通过。PC记录不是硬件验收。
- BOARD：两个独立新租约窗口、共{audit['real_PL_calls']}次真实PL调用。各72份权重只加载一次，148显式BO共140591104字节；两个manager与四个worker正常exit0。独立和延时完整扫描通过，默认PL/GDM恢复、无ZOCL/active lease/持锁者。没有强杀、重启、断电、刷写或音频动作。
- 12行off/on、CPU/PL结果的token、文本、EOS、prefill logits摘要与健康版匹配，状态清空字段正常。本轮没有重做逐层Y/原始混合状态比较；程序与数学未变，不能称新增全层bit-exact证明。

## 实测natural_profile的PL prefill

实际1008条submit按单在途执行顺序与原生prefill/decode调用计数核对，decode为432条。没有按次数摊分总耗时，普通profile=false样本保留未归属阶段。

原生许可等待 **{prefill['native_permission_wait_ms']/1000:.6f}秒**；管理端处理墙时 **{prefill['manager_wall_ms']/1000:.6f}秒**，许可线程CPU **{prefill['manager_thread_cpu_ms']/1000:.6f}秒**。下列互斥项之和等于管理端墙时：

| 管理端互斥分项 | 秒 |
|---|---:|
{rows}

下列是上述父区间内的子项，不能再次与父项相加；部分未单列的装配/锁/计时/函数工作保留在余额：

| 嵌套子项 | 秒 |
|---|---:|
{nestedrows}

原生许可等待与管理端墙时之差为 **{prefill['channel_client_scheduling_remainder_ms']/1000:.6f}秒**，包括通道、C++客户端处理、调度及边界差异，不能命名纯IPC。decode对应原生许可 **{decode['native_permission_wait_ms']/1000:.6f}秒**、管理端 **{decode['manager_wall_ms']/1000:.6f}秒**。完整分项、线程CPU、上下文切换原始记录见ACCOUNTING.json及on/readback-v1中的management-profile.json。

## 观测扰动

| 样本 | off完整结果秒 | on完整结果秒 | 变化 |
|---|---:|---:|---:|
{timingrows}

每模式每样本一次、off先on后，未随机化。这些变化同时受观测和运行漂移影响，不作统计显著性或新优化收益。逐许可只追加有界内存观测，原许可记录的检查/fsync/回复顺序保留；诊断文件在原客户端计时结束后统一写出。进程CPU差值覆盖start_request到摘要构建，包含计时结束后的聚合；与客户端t0/t2单列。

表中S1为CPU、S2为PL。启动、72次加载及关闭仍在原events.jsonl按许可类型分别记账；本观察器细粒度span只导出当前generate请求，生命周期未测的持久记录耗时为null。idle检查独立，不能与串行许可或CPU线程时间混加。同名嵌套decision span先按原始时间区间取并集，再构成互斥账；不重复累计父子时间。

## 交付、失败与后续

PROFILE_SCHEMA.json定义边界和嵌套；ACCOUNTING.json给出prefill/decode和生命周期账；HOTSPOTS.json给出排序；OBSERVER_OVERHEAD.json保存所有配对样本；BOARD_AUDIT.json是实际核验结果。source是独立派生，off/on/bundle-v1与回读原件、包边界审计和原始argv/退出码/日志全部保留。

首版AST转换缺位置信息导致exit1，已定位修复；原失败日志和source-attempt01—04保留。首次非交互认证exit255后按用户授权在隐藏提示认证，凭据未写入文件/参数/环境。无板故障注入不代替危险BOARD故障。失败细节见FAILURES.json。

下一项02根据本次大项及其子项选择等价实现优化；每次新鲜观察、动态锁/boot/资源检查、持久许可确认和失败隔离继续保留。默认回退基线仍是00冻结的健康包；新窗口不能复用本轮lease/boot/PID/launch。1022-token健康版、危险DMA故障、硬件周期/功耗/物理峰值和医学审核仍NOT_TESTED/null。实际会话模型设置unknown，子代理0。
'''
    save(OUT/'REPORT.md',report)
    entry=dict(status=audit['status'],updated_beijing=now,report=REL+'/REPORT.md',real_PL_calls=audit['real_PL_calls'],
        PC_tests=13,AST_equivalent_files=8,peer01A_03_changed=False,ARM_xclbin_math_unchanged=True,
        default_FPGA_enabled=False,A12_step11='PENDING',next='02_NOT_STARTED',full_01='01A_PEER_PENDING',
        actual_model_settings='unknown',subagents=0)
    def status(text):
        assert '"a12_cpu01b_20261024"' not in text
        a=text.index('{')+1;payload='\n  "a12_cpu01b_20261024": '+json.dumps(entry,ensure_ascii=False,indent=2).replace('\n','\n  ')+','
        result=text[:a]+payload+text[a:]
        assert {k:v for k,v in json.loads(result).items() if k!='a12_cpu01b_20261024'}==json.loads(text)
        return result
    edit('docs/PROJECT_STATUS.json',status)
    summary=f"2026-10-24 A12 CPU优化01B完成：{audit['status']}。13项Linux PC控制路径、8文件观测去除AST等价核对通过；两个独立顺序BOARD窗口共{audit['real_PL_calls']}真实PL调用，manager/worker正常exit0，独立及延时恢复检查通过。实际prefill/decode逐条归属和管理/健康/持久记录/通道余额、观察扰动已分账；同程序/库/位流，输出摘要匹配。01A/03未改，02未实施；全01仍待队友01A。A12第11步与默认FPGA关闭保持。证据 `{REL}/REPORT.md`。"
    for name in ('docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md'):
        edit(name,lambda text:summary+' 下方保留历史。\n\n'+text)
    def plan(text):
        marker='### 01｜补足最小诊断，先回答时间花在哪里';end='### 02｜压缩每次提交的CPU管理开销'
        a,b=text.index(marker),text.index(end);section=text[a:b]
        section=section.replace('- [ ] 许可端按prefill/decode分别记录','- [x] 许可端按prefill/decode分别记录',1)
        section+='**2026-10-24：01B已完成有界PC/BOARD诊断，01A仍待队友候选。** 证据 [`REPORT.md`](../'+REL+'/REPORT.md)。节点分类项不追认，02未实施。\n\n'
        return text[:a]+section+text[b:]
    edit('docs/A12_CPU_OPTIMIZATION_PLAN_20261024.md',plan)
    save(ROOT/'docs/handoffs/A_A12_CPU01B_20261024.md',f'# A12 CPU01B交接\n\n{summary}\n\n实际账本与限制见报告；下一项02，不修改队友01A/03。独立候选和原健康版回退均保留，旧许可不可复用。\n')
    preserved={}
    for batch in ('20261024-health-opt-v1','20261024-cpu-opt-00-v1'):
        base=ROOT/'evidence/model_pl_A'/batch
        for name,row in j(base/'SEAL.json')['files'].items():
            path=base/name;assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
        preserved[batch]=len(j(base/'SEAL.json')['files'])
    save(OUT/'HISTORICAL_PRESERVATION.json',dict(status='PASS_BYTES_UNCHANGED',files=preserved))
    save(OUT/'CLOSEOUT.json',dict(status='CPU01B_COMPLETE_WITH_LIMITATIONS',updated_beijing=now,
        all_previous_global_fields_preserved=True,prior_evidence=preserved,model_settings='unknown',subagents=0))
    print(json.dumps(dict(status='CPU01B_CLOSED',preserved=preserved)))


if __name__=='__main__':main()
