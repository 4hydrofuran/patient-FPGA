"""Record actual matched board samples and original-service restoration."""
from datetime import datetime,timezone,timedelta
import hashlib,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];EV=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=read(EV/'BASELINE.json');b=read(EV/'CANDIDATE.json');comparison=read(EV/'COMPARISON.json')
final=read(EV/'restore-user-mode-command/stdout.txt')['inventory']
restored=read(EV/'restored-progress-command/stdout.txt')['inventory']
baseline_poll=read(EV/'baseline-progress-v2-command/stdout.txt')['inventory']
candidate_poll=read(EV/'candidate-results-command/stdout.txt')['inventory']
assert comparison['actual_backend']=='FPGA_REAL' and comparison['BOARD']=='MEASURED'
assert len(a['rows'])==len(b['rows'])==4 and comparison['metrics']['native']['reduction_percent']<0
assert final['status']=='ORIGINAL_SERVICE_AND_USER_MODE_READY' and final['http']['ready'] and not final['http']['busy']
assert final['nice10_applied'] is False and final['user_turn_count']==0
assert final['http']['answer_cache']['entries']==1320
release={name:p['windows'][name]['files']['continuous/bundle/run-v1/result.json'] for name,p in (('baseline',baseline_poll),('candidate',candidate_poll))}
for value in release.values():assert value['worker_exit_code']==0 and value['lease_archived'] is True
def med(report,key):return statistics.median(row[key] for row in report['rows'])
record_a=statistics.median(r['permission']['durable_permission_record_ms'] for r in a['rows'])
record_b=statistics.median(r['permission']['durable_permission_record_ms'] for r in b['rows'])
metrics=dict(native_request_ms=dict(baseline=med(a,'native_request_wall_ms'),candidate=med(b,'native_request_wall_ms')),
    permission_wait_ms=dict(baseline=med(a,'permission_wait_ms'),candidate=med(b,'permission_wait_ms')),
    synchronous_record_ms=dict(baseline=record_a,candidate=record_b),
    backend_service_ms=dict(baseline=med(a,'backend_service_ms'),candidate=med(b,'backend_service_ms')))
for v in metrics.values():v.update(candidate_minus_baseline_ms=v['candidate']-v['baseline'],candidate_change_percent=100*(v['candidate']/v['baseline']-1))
now=datetime.now(timezone(timedelta(hours=8))).isoformat()
entry=dict(status='BOARD_NICE10_CANDIDATE_REJECTED_ORIGINAL_SERVICE_RESTORED',recorded_at=now,
    BOARD='MEASURED',selected_nice_adjustment=0,candidate_nice_adjustment=10,candidate_adopted=False,
    actual_backend_of_comparison='FPGA_REAL',samples_per_variant=4,answer_cache_used_in_comparison=False,
    same_model_prompt_output_tokens_prefix_and_call_shapes=True,per_question_pl_calls=[r['native_pl_calls'] for r in a['rows']],
    metrics=metrics,releases=release,measurement='NATIVE_REQUEST_HOST_WALL_INCLUDING_PREFIX_RESTORE; NOT_BROWSER_PAINT',
    nested_scope='SYNCHRONOUS_RECORD_IS_WITHIN_PERMISSION_WAIT; DO_NOT_ADD_PARENT_AND_CHILD',
    sample_scope='TWO_FIXED_QUESTIONS_TWO_REPEATS_PER_VARIANT; NOT_P95',
    boot_id='98886b24-96d3-409e-a783-ce9c54873da9',kernel='6.8.12-a10irq2',reboots_this_task=0,
    comparison_package='release/a12_permission_scheduler_noboard_20261027_v2',
    evidence=str(EV.relative_to(ROOT)),handoff='docs/handoffs/A12_PERMISSION_SCHEDULER_BOARD_COMPARISON_20261028.md',
    service_restore=dict(status='READY',window='a12-case20-debug-permission-restore-20261028-v1',
        runtime_root='/var/lib/kv260-a12/case20-debug-permission-restore-20261028-v1',
        original_source_manifest_sha256=final['original_source_sha256'],ready=True,busy=False,
        backend=final['http']['backend'],cases=20,cache_entries=1320,session=final['session'],user_turn_count=0,
        owner_pid=restored['lease']['pid'],owner_intentionally_retained=True,
        remaining_seconds=final['http']['remaining_seconds'],normal_release='PENDING_WHILE_USER_SERVICE_RUNNING'),
    hardware_cycles=None,remote_pushed=False,current_runtime=True,
    evidence_sha256={p.name:sha(p) for p in (EV/'BASELINE.json',EV/'CANDIDATE.json',EV/'COMPARISON.json')})
save(EV/'RESULT.json',entry)
save(ROOT/'release/a12_permission_scheduler_noboard_20261027_v2/BOARD_RESULT.json',entry)
p=ROOT/'docs/PROJECT_STATUS.json';old=read(p)
if 'a12_cache_debug_board_20261027' in old:
    old['a12_cache_debug_board_20261027'].update(current_runtime=False,
        superseded_by='a12_permission_scheduler_board_20261028',
        closure_this_task='NORMAL_WORKER_EXIT0_DEFAULT_RESTORE_LEASE_ARCHIVED_USER_RECORDS_PRESERVED')
if 'a12_permission_scheduler_no_board_20261027' in old:
    old['a12_permission_scheduler_no_board_20261027'].update(followup_board_status='NICE10_REJECTED_REGRESSION',
        followup_board_report=entry['handoff'])
old.pop('a12_permission_scheduler_board_20261028',None)
save(p,{'a12_permission_scheduler_board_20261028':entry,**old})
rows='\n'.join('| '+name+' | '+f"{v['baseline']/1000:.3f} s | {v['candidate']/1000:.3f} s | {v['candidate_change_percent']:+.2f}% |" for name,v in (
    ('原生模型请求',metrics['native_request_ms']),('许可往返',metrics['permission_wait_ms']),
    ('同步日志记录（许可内部）',metrics['synchronous_record_ms']),('后端计算及数据处理',metrics['backend_service_ms'])))
detail='\n'.join('| '+x['question']+' | '+str(x['repeat']+1)+' | '+f"{x['native_request_wall_ms']/1000:.3f} s | {y['native_request_wall_ms']/1000:.3f} s |" for x,y in zip(a['rows'],b['rows']))
doc=f'''# KV260许可调度候选：实板对比与原服务恢复

记录时间：{now}（北京时间）。本次从10月27日晚跨至28日凌晨，boot和kernel保持一致，无重启。

结论：nice+10候选未通过性能采用条件，已恢复原调度及原二十例缓存调试服务。四条配对样本的原生请求中位数由13.493秒变为14.671秒，增加1.178秒、8.73%；许可和同步日志记录也未改善。此前CPU验证只证明功能和输出一致，未作为实板收益。

## 相同工作量的实测

两组各4次：SYN_CP_03的持续时间、疼痛程度问题，各重复两次。均明确旁路答案缓存、MODEL/FPGA_REAL、原checker与EOS通过。模型/库身份、原生参数、提示哈希、输出token、前缀及调用形状均由比较器核对一致。

| 指标（四次样本中位数） | 原调度 | nice+10候选 | 候选变化 |
| --- | ---: | ---: | ---: |
{rows}

同步日志记录包含JSON编码、写入及fsync期间的时间，已包含在许可往返中，不能相加，也不能全部称为纯磁盘耗时。后端计算及数据处理是许可之外的嵌套计时范围，没有设备周期计数。

| 问题 | 重复 | 基线原生耗时 | 候选原生耗时 |
| --- | ---: | ---: | ---: |
{detail}

八次实际输出：持续时间均为“一回大约疼 20 分钟。”，疼痛程度均为“满分 10 分的话我有 5 分。”。每条实际288次PL调用，两组各1152次测量内调用。前缀预热、模型及硬件产物相同；同步fsync和许可处理函数保持原实现。

计时范围为原生请求宿主时间，包含前缀恢复，不包含浏览器绘制。本包使用二十例自然表达策略，工作量与原三例48-token/216调用请求不同，因此旧10.68秒和4.83秒不是本次配对基线。四条样本不足以给出p95或普遍性能结论，但本次数据不支持采用nice+10。没有把缓存命中或CPU数据当成实板提速。

## 窗口与恢复

原缓存调试Owner先正常关闭并归档，用户记录保留。基线窗口 `a12-permission-baseline-20261027-v1`、候选窗口 `a12-permission-candidate-20261027-v1` 均经原Owner完成worker退出0、平台恢复和租约归档；两组旧窗口没有保留活动硬件租约。日志中的历史NORMAL_RESTORE_PENDING_AUDIT状态原样保留，不追认为另做过发布审计。

随后从原阶段目录恢复了完全相同的缓存调试源码，源清单SHA256为 `{final['original_source_sha256']}`，没有加入nice+10。恢复窗口 `a12-case20-debug-permission-restore-20261028-v1`，Owner PID={restored['lease']['pid']}。随机抽例、CPU/FPGA选择、缓存调试开关及1320条目录保留，测试前的CPU界面模式已恢复。服务ready=true、busy=false，已留下0条提问的新会话 `{final['session']['session_id']}`。

恢复时原入口的真实图形FPGA探针通过，之后恢复答案缓存。该探针是另一随机病例，不纳入本次四对性能统计。当前Owner为用户服务而保留，不能把它与两个已释放测试窗口混淆；停止整个服务仍走原 `continuous/stop-request.json` 流程。

## 产物与已保留问题

数据入口：`{EV.relative_to(ROOT).as_posix()}/RESULT.json`；原始配对文件BASELINE.json、CANDIDATE.json及COMPARISON.json的SHA256均已记录。各命令目录保留真实命令、退出码和stdout/stderr。

传输阶段出现一次Windows CRLF与Linux LF导致的派生清单差异，修正后两份清单与本地无板验证版本逐字节一致；失败回执保留，原服务在传输确认前未停止。启动脚本曾在读取含空格的/proc进程名时解析失败，发生在旧结果页关闭或新计算窗口启动前，修正后执行成功。它们没有被算成性能样本。

比较器CLI补充了显式UTF-8/BOM读取；Windows和WSL对同一真实结果均完成比较，比较算法与已测包一致。未改动已消费的板端对比包。

本次不采纳nice+10。若继续优化，应针对许可协议与同步日志路径本身重新设计并配对测量，不能以调度假设或PC微小差异代替板端结果。
'''
(ROOT/entry['handoff']).write_text(doc,encoding='utf-8')
print(json.dumps(dict(status=entry['status'],metrics=metrics,service_ready=True,nice10_adopted=False),ensure_ascii=False,indent=2))
