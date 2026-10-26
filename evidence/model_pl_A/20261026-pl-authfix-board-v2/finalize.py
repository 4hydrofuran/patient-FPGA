import hashlib,json,zipfile
from pathlib import Path
here=Path(__file__).parent
repo=here.parents[2]
def uart(name):
 r=json.loads((here/name).read_text(encoding='utf-8-sig'))
 assert r['error'] is None
 return json.loads(r['output'].split('__PL_BEGIN__',1)[1].split('__PL_END__',1)[0].strip())
export=uart('collect-uart.json')
archive=here/'board-receipt.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==export['sha256']
out=here/'board-receipt';out.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z:z.extractall(out)
attempt=json.loads((out/'ATTEMPT_RESULT.json').read_text(encoding='utf-8'))
native=attempt.get('run-v1/result.json',{})
pair=attempt.get('run-v1/s2/ordinary-pair-comparison.json',{})
restored=not export['active_lease'] and not export['zocl'] and export['overlays']=={'k26-starter-kits_image_1':'applied'}
passed=attempt['status']=='NORMAL_MANAGER_EXIT' and attempt['exit_code']==0 and pair.get('equal') is True and restored
status='PASS_ORDINARY_R0_WARM_HIT_BOARD' if passed else 'FAILED_PL_ACCEPTANCE_ATTEMPT'
summary=dict(status=status,verification_level='BOARD',boot_id=export['boot_id'],kernel=export['kernel'],
 workload_authorization_included=False,owner_review_authorized_compute=True,
 permission_submissions=native.get('permission_submissions'),hardware_global_count=None,
 manager_exit_code=attempt['exit_code'],ordinary_pair_equal=pair.get('equal'),
 platform_restored=restored,active_lease=export['active_lease'],zocl=export['zocl'],
 heavy_diagnostics=False,old_failure_preserved=True,full_numeric_acceptance='NOT_PERFORMED',
 production_ready=False,board_resident_service='NOT_TESTED',cases=attempt['cases'],
 receipt_zip_sha256=export['sha256'])
(here/'RESULT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# A12 授权字段修复与普通 PL 验收（2026-10-26）','',f'结论：**{status}**。','',
 '修复将工作量 spec.authorization_included 保持 false；计算授权单独绑定原 Owner review。新增绑定函数复用原 validate_plan，并在驱动/PL 加载前完成工作量校验；不放宽原策略。旧错误脚本、失败窗口与冻结包不覆盖。',
 '', '定向 PC 验证：历史契约、新版配置、四项绑定与真实应用适配器导入回归、一项普通三请求控制链测试均退出0。控制链测试使用明确的替身，不算PL证据。',
 '', '本次任务按三次明确授权累计执行3次正常重启、2次临时irq2引导；无强制复位、断电命令、刷写、saveenv或默认启动文件更改。旧启动的失败租约在锁与原占用检查后原样归档。v1及更早失败证据不覆盖。',
 '', '前件v1先因短生命周期进程退出造成占用扫描不完整而中止；随后实际FPGA_REAL worker就绪、72权重加载、0次提交，但首个请求前发现measure_application未导入。该打包缺陷已修复，真实派生管理器导入回归通过，并把依赖解析提前至Owner创建前。旧管理器仅有finalize-only通道，故经用户授权正常重启恢复。恢复重启关机耗时超过旧100秒捕获窗口、错过倒计时；板子实际正常回默认系统。捕获窗口延长至300秒后再次正常重启并临时引导成功。',
 '', '串口登录等待超时及提示符重新获取失败保留；首份超时记录的登录输入已脱敏。另有本机UTF-8报告编码与PowerShell生成脚本引号错误，均在发送对应板端操作前修正；没有因此重复模型请求。',
 '',f"实际启动：`{export['boot_id']}` / `{export['kernel']}`。原普通工作量为 R0 / warm / hit，107 / 70 / 37 个新提示词 token，输出上限8，72权重加载和5000总提交上限保持。未新增长前缀诊断、全状态导出或历史原件扫描。",'']
for name,case in attempt['cases'].items():
 lines.append('## '+name)
 lines.append('')
 lines.append('```json\n'+json.dumps({k:v for k,v in case.items() if k!='result.json'},ensure_ascii=False,indent=2)+'\n```')
 q=case.get('result.json',{})
 if q:lines.append('原生结果：'+json.dumps({k:q.get(k) for k in ('status','text','eos','decode_calls','state_cleared_before_response')},ensure_ascii=False))
 lines.append('')
lines.extend([f"普通R0/hit比较：{pair.get('equal')}；管理器退出码：{attempt['exit_code']}；平台恢复：{restored}；活动租约：{export['active_lease']}；ZOCL：{export['zocl']}。",'',
 '通过范围仅为这一组普通模型输出、前缀复用和资源流程；不追认为全面数值验收、长期稳定性、常驻候选服务或生产可用。硬件全局计数仍null；提交数是原权限/后端完成证据。', '',
 '证据：RESULT.json、PC_CHECKS.json、BASELINE_REVIEW.json、boot-after-archive.json、start-uart.json、collect-uart.json、board-receipt.zip及解包目录。'])
(here/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
path=repo/'docs/PROJECT_STATUS.json'
state=json.loads(path.read_text(encoding='utf-8'))
key='a12_pl_authorization_fix_board_repaired_20261026'
assert key not in state
state[key]={k:summary[k] for k in ('status','boot_id','kernel','workload_authorization_included','owner_review_authorized_compute','permission_submissions','manager_exit_code','ordinary_pair_equal','platform_restored','active_lease','zocl','heavy_diagnostics','production_ready','board_resident_service')}
state[key]['evidence']='evidence/model_pl_A/20261026-pl-authfix-board-v2/REPORT.md'
state[key]['previous_failed_lease_preserved_in_history']=True
path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='cases'},ensure_ascii=False))
for name,case in summary['cases'].items():
 print(name,json.dumps({k:v for k,v in case.items() if k!='result.json'},ensure_ascii=False))
