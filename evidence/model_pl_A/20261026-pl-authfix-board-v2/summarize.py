import hashlib,json,shutil
from pathlib import Path
here=Path(__file__).parent;repo=here.parents[2]
r=json.loads((here/'RESULT.json').read_text(encoding='utf-8'))
assert r['status']=='PASS_ORDINARY_R0_WARM_HIT_BOARD'
cases=r['cases'];a=cases['app_R0']['application-timing.json'];b=cases['app_hit']['application-timing.json']
startup=json.loads((here/'board-receipt/bundle/run-v1/s2/startup-timing.json').read_text())
resources=json.loads((here/'board-receipt/bundle/run-v1/s2/resource-probe-summary.json').read_text())
summary=dict(status=r['status'],R0_verified_answer_s=a['complete_app_ms']/1000,hit_verified_answer_s=b['complete_app_ms']/1000,
 verified_answer_saved_s=(a['complete_app_ms']-b['complete_app_ms'])/1000,
 verified_answer_reduction_percent=100*(1-b['complete_app_ms']/a['complete_app_ms']),
 R0_internal_first_token_s=a['TTFT_app_ms']/1000,hit_internal_first_token_s=b['TTFT_app_ms']/1000,
 internal_first_token_reduction_percent=100*(1-b['TTFT_app_ms']/a['TTFT_app_ms']),
 native_startup_to_ready_s=(startup['ready_received_monotonic_ns']-startup['process_launch_monotonic_ns'])/1e9,
 warm_s=cases['warm_prefix']['client-timing.json']['result_wall_ms']/1000,
 text=cases['app_hit']['result.json']['text'],sample_pairs=1,
 permission_submissions=2880,hardware_global_count=None,
 stage_sample_minimum_kib=resources['sampled_minimum_kib'],continuous_peak_memory=None,
 platform_restored=True,active_lease=False,zocl=False,within_10s=False)
(here/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
checks=json.loads((here/'PC_CHECKS.json').read_text(encoding='utf-8'))
checks['checks'].append(dict(command='python3 -B -m unittest -v test_resource_probe_binding test_resource_probe.CaseTests.test_ordinary_pair_completes_without_diagnostics',exit_code=0,tests=7,log='targeted-tests.txt'))
checks['retained_development_failure']='Initial new scan-policy regression lacked the frozen a10 module search path (ModuleNotFoundError); path fixed, final seven targeted tests pass.'
checks['BOARD']=r['status']
(here/'PC_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
source_pins={}
for name in ('platform/qwen35/a12/cpu01b_window.py','control/resource_probe_manager.py','platform/qwen35/a12/resource_probe_binding.py'):
 actual=here/'board-receipt/bundle'/name;candidate=here/'bundle-fixed-v2'/name
 digest=hashlib.sha256(actual.read_bytes()).hexdigest()
 assert hashlib.sha256(candidate.read_bytes()).hexdigest()==digest
 source_pins[name]=digest
(here/'TESTED_SOURCE_PINS.json').write_text(json.dumps(dict(tested_sources=source_pins,
 reusable_unbound_package_sha256='55cb8fd6892c71c4c2989bf375950ae971179195fbc0809f6207fdf0131980e2',
 native_binary_sha256='115d167265667f026594836760be12470876e2b001b9dc8b61773459da35efab',
 native_binary_changed=False,public_ABI_changed=False),indent=2)+'\n',encoding='utf-8')
shutil.copyfile(here/'REPORT.md',here/'REPORT-generated-v1.md')
lines=['# 授权修复与普通PL验收结果（2026-10-26）','',
 '**PASS_ORDINARY_R0_WARM_HIT_BOARD**。真实板端普通R0、前缀预热和hit完成，原内容检查与EOS通过，R0/hit输出及最后prefill logits摘要一致。仅一组合成病例测试，不代表全面数值、长期稳定性、医学或生产验收。','',
 '## 实际应答时延','',
 '| 指标 | R0 | hit | 减少 |','| --- | ---: | ---: | ---: |',
 f"| 输入至完整核验回答 | {summary['R0_verified_answer_s']:.3f}秒 | {summary['hit_verified_answer_s']:.3f}秒 | {summary['verified_answer_saved_s']:.3f}秒（{summary['verified_answer_reduction_percent']:.2f}%） |",
 f"| 输入至内部首token | {summary['R0_internal_first_token_s']:.3f}秒 | {summary['hit_internal_first_token_s']:.3f}秒 | {summary['internal_first_token_reduction_percent']:.2f}% |",'',
 f"两轮均回答“{summary['text']}”。完整核验回答更接近用户可获得应答的时间；内部首token尚未经最终内容核验，不等于界面已经交付。计时包含原Session路由、模板、分词、计算及检查，排除模型加载、会话构建和外部终端传输。未达到10秒内应答。仅一次配对，无p95或稳定提速保证。",'',
 f"原生进程启动至ready为{summary['native_startup_to_ready_s']:.3f}秒；70token前缀预热另需{summary['warm_s']:.3f}秒。它们均未计入上表输入时延，ready本身不代表服务已完成预热。",'',
 '## 修复内容','',
 '1. 工作量spec.authorization_included保持false；计算授权独立绑定Owner review。工作量仍由原validate_plan校验。',
 '2. 修复打包器遗漏measure_application导入，使用原tt10_00_app.measure；依赖解析提前至Owner及PL加载前。',
 '3. 初始占用扫描复用现有complete_scan策略：最多4次，仅对明确的瞬时进程变化重采样；必须获得完整无占用扫描，实际设备占用和未知错误仍立即拒绝。原释放检查和硬件门槛保持。',
 '4. 串口登录处理人工输入等待超时；恢复重启的被动捕获窗口由100秒延长到300秒，避免错过临时引导。', '',
 '原模型/原生二进制、公共数学与ABI未变。最终7项定向PC回归退出0，日志targeted-tests.txt；包重新生成并验证。实际板测的三个修改源码与可复用包字节一致，见TESTED_SOURCE_PINS.json。', '',
 '## 实际执行与恢复','',
 f"内核6.8.12-a10irq2，boot `{r['boot_id']}`。权重仅加载72次，显式BO共148个、140591104字节；R0/warm/hit实际权限提交分别1440/648/792，总计2880，后端完成数互认。硬件全局计数未测，保持null。",'',
 'R0处理107个新提示词token；hit实际复用70个，仅处理37个新token。两轮各6次decode调用。没有重型诊断、全位置logits导出、原始状态文件或历史原件全量核对。', '',
 f"8次阶段资源采样中CmaFree最低{resources['sampled_minimum_kib']['CmaFree']}KiB（{resources['sampled_minimum_kib']['CmaFree']/1024:.3f}MiB）；资源观察日志{resources['observation_bytes']}字节。未触发资源门槛；不是连续峰值测量。",'',
 'worker退出0，管理器退出0；原FD/VMA/refcount及内核检查后正常卸载测试PL/ZOCL，恢复默认PL/GDM并归档租约。随后的独立只读回执确认活动租约为空、ZOCL不存在、默认overlay applied。板子仍上电，当前内核仍为临时irq2。', '',
 '## 保留的失败和边界','',
 'v1及本目录首次入口因短生命周期进程退出而中止，未加载PL；v1第二次入口在72权重加载、0次提交后因缺失应用适配器失败。其现场保留，随后经用户授权正常重启恢复，旧lease原样归档，旧worker正常退出码仍未知。旧100秒捕获窗口错过一次倒计时，系统实际正常回默认内核；延长窗口后再临时引导成功。', '',
 '本次任务按三次明确授权累计3次正常重启、2次临时irq2引导；没有强制复位、断电命令、刷写、saveenv或默认启动文件更改。串口登录、UTF-8报告编码、PowerShell生成引号及测试搜索路径的开发失败保留；登录输入脱敏，没有据此追记PL通过。', '',
 '这次通过的是普通资源探测链；新的短提示词常驻候选尚未在板上运行，未因本次结果记为通过。可复用bundle-fixed-v2.zip仍为UNBOUND，无可重放的计算授权。', '',
 '原始证据：RESULT.json、SUMMARY.json、board-receipt.zip及解包目录、start2-uart.json、collect-uart.json、BASELINE_REVIEW.json、fix-initial-scan.json、全部启动和前件失败回执。']
(here/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
status_path=repo/'docs/PROJECT_STATUS.json';state=json.loads(status_path.read_text(encoding='utf-8'))
entry=state['a12_pl_authorization_fix_board_repaired_20261026']
entry.update(verified_answer_R0_s=summary['R0_verified_answer_s'],verified_answer_hit_s=summary['hit_verified_answer_s'],
 verified_answer_reduction_percent=summary['verified_answer_reduction_percent'],sample_pairs=1,within_10s=False,
 fixes=['workload authority separated from Owner','original application adapter import','existing bounded complete scan at initial admission'],
 reusable_unbound_package='evidence/model_pl_A/20261026-pl-authfix-board-v2/bundle-fixed-v2.zip')
status_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='text'},ensure_ascii=True))
