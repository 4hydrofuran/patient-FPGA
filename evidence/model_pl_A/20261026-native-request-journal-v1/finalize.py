"""Freeze this actual-PC integration stage; the broader goal remains active."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
PROBE=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1'
HANDOFF=ROOT/'docs/handoffs/A_A12_NATIVE_REQUEST_JOURNAL_PC_20261026.md'


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,message):
    if not ok:raise RuntimeError(message)
def save(p,obj):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def row(p):return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))


for receipt,key in [(PROBE/'FINAL_REVIEW.json','code'),
    (ROOT/'evidence/model_pl_A/20261025-offline-followup-v1/FINAL_REVIEW.json','source'),
    (ROOT/'evidence/model_pl_A/20261025-request-journal-v2/FINAL_REVIEW.json','source')]:
    for r in read(receipt)[key]:
        p=Path(r['path']) if Path(r['path']).is_absolute() else ROOT/r['path']
        need(p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'prior source changed: '+str(p))
baseline=read(PROBE/'BASELINE.json');parent=Path(baseline['parent_bundle'])
for r in baseline['parent_files']:
    p=parent/r['path'];need(p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'parent payload changed')
for r in baseline['contract_files']:
    p=Path(r['path']);need(p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'public contract changed')
need(sha(PROBE/'bundle-v2.zip')=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa','ordinary probe ZIP changed')
need(sha(PROBE/'bundle-v2/manifest.json')=='4fcb6af2d9e7d5b89f876697de6bd8f11e36174666169544a9016009551f070f','ordinary manifest changed')
need(sha(ROOT/'system_qwen35/app/checking.py')==sha(ROOT/'evidence/model_pl_A/20261025-short-prompt-offline-v3/application/system_qwen35/app/checking.py'),'default prompt/checker changed')
native=read(OUT/'FINAL_NATIVE_CHECKS.json');need(native['status']=='PASS_REAL_PC_NATIVE_REQUEST_JOURNAL_AND_FAILURE_FENCES','native evidence not passed')
need(native['result_delivery_after_END_proven'] and len(native['faults'])==3,'delivery/failure proof missing')
for r in read(OUT/'COLLECTED_BUILD.json')['files']:
    p=OUT/'pc-build'/r['name'];need(p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'collected build changed')
need(sha(OUT/'pc-build/liba12_native_cpu_control.so')==read(OUT/'BUILD-v2.json')['library_sha256'],'PC adapter bytes changed')

names=('native_cpu_control.cpp','native_cpu_build.py','native_cpu_abi_probe.py','test_native_cpu_adapter.py',
       'native_request_journal.py','native_request_run.py','native_request_audit.py','test_native_request_integration.py',
       'native_cpu_artifact_audit.py','native_request_review.py')
snapshot=OUT/'source';snapshot.mkdir(exist_ok=False);sources=[]
for name in names:
    p=ROOT/'platform/qwen35/a12'/name
    if p.suffix=='.py':compile(p.read_text(encoding='utf-8'),str(p),'exec')
    shutil.copyfile(p,snapshot/name);need(sha(p)==sha(snapshot/name),'source snapshot differs');sources.append(row(p))

remaining=[
 dict(id='P0-0',requirement='Freeze versions/ordinary resource baseline',offline='ORDINARY_PACKAGE_AND_PC_NATIVE_VERIFIED',
      BOARD='NOT_TESTED',evidence='docs/handoffs/A_A12_RESOURCE_PROBE_PREBOARD_20261025.md'),
 dict(id='P0-1',requirement='Bounded complete-original handoff and numerical gates',offline='PC_FULL_RAW_HANDOFF_PASSED_PRIOR_SCOPE',
      BOARD='NOT_TESTED',evidence='docs/handoffs/A_A12_OFFLINE_FOLLOWUP_20261025.md'),
 dict(id='P1-1',requirement='Request journal integrated with real native',offline='REAL_PC_MODEL_AND_FAILURE_FENCES_PASSED',
      real_PL_controller_binding='NOT_IMPLEMENTED',evidence=HANDOFF.relative_to(ROOT).as_posix()),
 dict(id='P1-2',requirement='Move static checks; bounded fresh periodic health and invalidation',offline='NOT_IMPLEMENTED',
      BOARD='NOT_TESTED',safety_parameters='MUST_DERIVE_FROM_EXISTING_REQUIREMENTS_NOT_ATTACHMENT_SUGGESTIONS'),
 dict(id='P1-3',requirement='Microbatch authorization, local budget/revocation/restart proofs',offline='NOT_IMPLEMENTED',BOARD='NOT_TESTED'),
 dict(id='P1-4',requirement='Mode selection, strict fallback and closeout',offline='PC_LOG_MODE_SELECTION_ONLY',
      production_mode_transition='NOT_IMPLEMENTED',BOARD='NOT_TESTED'),
 dict(id='SHORT_PROMPT',requirement='Safe/fast new prompt accepted on all frozen inputs',offline='NOT_ACCEPTED',
      evidence='evidence/model_pl_A/20261025-request-journal-v2/short-prompt-review-01/RESULT.json'),
 dict(id='FINAL_ACCEPTANCE',requirement='Applicable numerical/lifecycle/TT10/A12 step11 and long-run acceptance',
      status='INCOMPLETE',medical_or_teacher_review='NOT_COMPLETED')]
save(OUT/'COMPLETION_AUDIT.json',dict(goal_objective='继续推进无板工作,遇到阻碍则分析原因，思考解决办法，解决问题',
    previous_turn_classification='progress',current_turn_classification='progress',whole_goal_achieved=False,
    goal_status='active',requirements_basis=['docs/A12_SAFETY_CHECK_OPTIMIZATION_PLAN_20261025.md',
    'docs/A12_CMA_AWARE_ACCEPTANCE_ADJUSTMENT_20261025.md'],requirements=remaining,
    next_safe_action='Read original owner/health/kernel-check call graph, implement/test P1-2 offline invalidation or monitor candidate without board activation',
    blockers_do_not_prevent_other_offline_work=True,board_work_still_excluded=True))
activation=dict(status='PC_NATIVE_INTEGRATED_UNBOUND_FOR_BOARD',board_execution_enabled=False,
    compute_authorization_included=False,production_default=False,original_resource_probe_changed=False,
    release_authority=False,replay_authority=False,BOARD='NOT_TESTED',board_latency_saving_s=None)
save(OUT/'ACTIVATION.json',activation)
scope=dict(status='ACTUAL_PC_NATIVE_REQUEST_JOURNAL_VALIDATED_GOAL_ACTIVE',report=HANDOFF.relative_to(ROOT).as_posix(),
    final_review='evidence/model_pl_A/20261026-native-request-journal-v1/FINAL_REVIEW.json',
    actual_PC_native_integration='PASS_PC_MATH_DOUBLE_REAL_CPU_OUTPUTS',real_PL_binding='NOT_IMPLEMENTED',
    final_ABI_tests=5,final_recorded_native_integration_tests=8,real_fault_cases=3,
    actual_cpu_calls_per_successful_window=2880,journal_rows=dict(strict=2962,request=82),
    final_PC_timings=native['A_B_PC_only'],model_process_windows=9,successful_model_windows=6,injected_fault_windows=3,
    new_short_prompt='NOT_ACCEPTED_NOT_USED',original_resource_probe_unchanged=True,
    BOARD='NOT_TESTED',new_PL_calls=0,board_latency_saving_s=None,board_CMA_improvement=None,
    overall_goal_complete=False,goal_status='active',actual_model_settings='unknown',DeepSeek_or_subagent_delegation=False)
save(OUT/'STATUS.json',scope)

block='''

## 2026-10-26 A12 请求日志真实PC模型接入，目标仍active

新增x86 PC专用许可适配层，转发到既有CPU数学库；原生程序/CPU库不重编译，不改B或公共数学/ABI。真实模型R0/warm/hit两版各2880次CPU投影、72权重加载、2959所有权/2958健康检查；最终普通输出/末位置logits/清理与原CPU及彼此一致。PC严格日志2962→请求日志82条，各有4份回执；最终同一冻结问题的完整答案R0 9.509→4.862秒、hit 5.005→2.267秒，仅各模式一个最终样本，不折算板端或p95。独立核对原生stdout、许可链、回执与END先于交付时序通过。

真实数组ABI 5项、已记录真实响应/审计8项及真实调用链3故障关口通过。BEGIN fsync失败0提交；END失败已算1440但0答案交付；首提交健康拒绝0转发，保留旧助手误分类链并报告真正健康原因。CPU进程合作exit2，不记正常关闭/板端释放，不强杀。旧job输出可消费标志的首版真实FAIL与测试框架命名错误原件保留；修复独立v2后复测。正常/故障均无重型诊断，PL=0，硬件计数null。

旧普通探测包、前轮源码/失败、168父包文件与5契约保持。没有上板、恢复、部署或推送；CMA/板端收益NOT_TESTED/null，短提示词仍NOT_ACCEPTED。P1-2检查位置/周期健康、P1-3微批授权、PL外层独立绑定/模式切换和最终验收仍待推进，不能说仅剩上板或目标已完成。复杂设计/ABI/验收无委派，模型设置unknown。交接 `docs/handoffs/A_A12_NATIVE_REQUEST_JOURNAL_PC_20261026.md`，证据/剩余审计 `evidence/model_pl_A/20261026-native-request-journal-v1/FINAL_REVIEW.json`、`COMPLETION_AUDIT.json`。
'''
backup=OUT/'governance-before';backup.mkdir(exist_ok=False);updates=[]
for name in ('DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md'):
    p=ROOT/'docs'/name;before=p.read_bytes();(backup/name).write_bytes(before)
    need('A12 请求日志真实PC模型接入，目标仍active'.encode() not in before,'duplicate governance entry')
    with p.open('ab') as f:f.write(block.encode())
    need(p.read_bytes()==before+block.encode(),'concurrent governance edit: inspect preserved bytes')
    updates.append(dict(path=p.relative_to(ROOT).as_posix(),before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=sha(p)))
p=ROOT/'docs/PROJECT_STATUS.json';before=p.read_bytes();(backup/p.name).write_bytes(before)
text=before.decode('utf-8-sig');old=read(p);key='a12_native_request_journal_pc_20261026';need(key not in old,'duplicate status')
lines=json.dumps(scope,ensure_ascii=False,indent=2).splitlines()
new='{\n  '+json.dumps(key)+': '+lines[0]+'\n'+'\n'.join('  '+line for line in lines[1:])+','+text[text.index('{')+1:]
parsed=json.loads(new);need(parsed.pop(key)==scope and parsed==old,'unrelated status changed')
need(p.read_bytes()==before,'concurrent status edit: stopped before write')
p.write_text(new,encoding='utf-8',newline='')
updates.append(dict(path=p.relative_to(ROOT).as_posix(),before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=sha(p)))
save(OUT/'GOVERNANCE_UPDATE.json',updates)

report='''# A12真实PC模型请求日志验证

详细结果见 [交接](C:/Patientqwen/docs/handoffs/A_A12_NATIVE_REQUEST_JOURNAL_PC_20261026.md)。
本轮已完成真实PC模型许可/日志接入与最终同工作量对照，普通结果/末位置logits/清理与原CPU一致。ABI 5项、记录响应/审计8项通过；真实BEGIN/END/健康故障均停止交付且保留失败。
最终PC完整答案R0 9.509→4.862秒、hit 5.005→2.267秒，仅同一问题各模式一个最终样本，非板端收益或p95。
源码和小型PC构建物、正常/失败原件副本已冻结；第一版标记FAIL和框架启动错误保留。没有新PL、BOARD、重型诊断、部署或推送。
完整目标未完成，COMPLETION_AUDIT.json逐项列出P1-2/P1-3、PL绑定、短提示词及最终验收缺口，goal保持active。
'''
with (OUT/'REPORT.md').open('x',encoding='utf-8') as f:f.write(report)
files=[p for p in OUT.rglob('*') if p.is_file() and 'governance-before' not in p.parts]
files.append(HANDOFF)
review=dict(status=scope['status'],recorded_at=datetime.now(timezone.utc).isoformat(),source=sources,
    evidence=[row(p) for p in sorted(files)],final_native_checks=native,activation=activation,
    immutable=dict(original_probe_zip_sha256=sha(PROBE/'bundle-v2.zip'),parent_files=168,public_contract_files=5,
        probe_source_files=7,prior_followup_source_files=6,prior_verified_journal_source_files=4,
        default_prompt_and_checker_unchanged=True,native_program_and_CPU_math_binary_unchanged=True),
    compilation_warning='Unchanged inherited prefix_cache.hpp warning retained; no all-warning-free claim',
    new_PL_calls=0,board_contacted=False,BOARD='NOT_TESTED',board_latency_saving_s=None,
    medical_or_teacher_review='NOT_COMPLETED',actual_model_settings='unknown',delegation='NONE_PROTECTED_SCOPE',
    Git_publication='NOT_PERFORMED',overall_goal_complete=False,goal_status='active')
save(OUT/'FINAL_REVIEW.json',review)
print(json.dumps(dict(status=scope['status'],source_files=len(sources),protected_parent_files=168,contracts=5,
    actual_PC_native='PASS',final_tests='5_ABI_PLUS_8_RECORDED_INTEGRATION',real_faults=3,
    BOARD='NOT_TESTED',goal_status='active'),indent=2))
