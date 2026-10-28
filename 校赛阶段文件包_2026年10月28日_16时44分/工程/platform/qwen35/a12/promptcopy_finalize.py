"""Seal the isolated facts-only PC result without enabling Board/default paths."""
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import zipfile
from promptcopy_candidate import ROOT,OUT,PARENT,CANDIDATE,read,save,sha,pin,prior

KEY='a12_facts_only_prompt_pc_20261026'
HANDOFF='docs/handoffs/A_A12_FACTS_ONLY_PROMPT_PC_20261026.md'
DOCS=('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md')

def local(path):
    text=str(path).replace('\\','/')
    return ROOT/text[len('C:/Patientqwen/'):] if text.startswith('C:/Patientqwen/') else Path(path)

def main():
    audit=read(OUT/'INDEPENDENT_AUDIT.json');assert audit['status']=='PASS_ACTUAL_CPU_RAW_OUTPUT_AUDIT' and audit['all_finite_content_pass'] and not audit['rejected']
    folder=OUT/CANDIDATE;summary=read(folder/'RESULT.json');assert summary['numerical_pairs']==25 and summary['policy_items']==7
    assert summary['quality_rejections']==[] and summary['worker_exit_codes']==[0,0] and summary['board_candidate_eligible'] is False
    baseline=read(OUT/'BASELINE.json')
    for row in baseline['files']:assert sha(ROOT/row['path'])==row['sha256']
    old_sources=read(PARENT/'PRESERVATION.json')['old_source_pins']+read(PARENT/'FINAL_REVIEW.json')['source']
    for row in old_sources:assert sha(ROOT/row['path'])==row['sha256']
    for row in read(OUT/'PLAN.json')['protected_default_sources']:assert sha(ROOT/row['path'])==row['sha256']
    probe=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1';original=read(probe/'BASELINE.json')
    for row in original['parent_files']:assert sha(local(original['parent_bundle'])/row['path'])==row['sha256']
    for row in original['contract_files']:assert sha(local(row['path']))==row['sha256']
    assert sha(probe/'bundle-v2.zip')=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    ready=read(folder/'native-PC/model-ready.json');runtime=[]
    # Resolve exact hashes from the already reviewed artifact registry. Some
    # mathematical DSOs are reached through the frozen ELF RPATH, not LD_PATH.
    pinned=read(PARENT/'ARTIFACT_REVIEW.json')['artifacts']
    for name,expected in ready['prefix_cache']['identity']['libraries'].items():
        matches=[Path(r['path']) for r in pinned if r['sha256']==expected and
            (Path(r['path']).name==name or Path(r['path']).name.startswith(name+'.')) and sha(r['path'])==expected]
        assert matches,'current CPU runtime missing: '+name
        runtime.append(dict(path=str(matches[0]),sha256=expected))
    assert sha(prior.BINARY)==summary['native_sha256'];runtime.append(dict(path=str(prior.BINARY),sha256=summary['native_sha256']))
    save(OUT/'RUNTIME_REUSE.json',dict(status='PASS_CURRENT_CPU_BINARY_AND_MATH_LIBRARY_HASHES',artifacts=runtime,rebuilt=False,ARM_execution='NOT_EXECUTED',BOARD='NOT_TESTED'))
    for label,script in [('HISTORICAL_CONTRACT_GUARD','scripts/release/check_contracts.py'),('QWEN35_CONFIG_GUARD','scripts/release/qwen35_config.py')]:
        cmd=[sys.executable,script];r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        save(OUT/(label+'.json'),dict(command=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));assert r.returncode==0
    timing={name:dict(min=min(row[name] for row in audit['rows']),median=statistics.median(row[name] for row in audit['rows']),max=max(row[name] for row in audit['rows']))
        for name in ('R0_complete_app_ms','hit_complete_app_ms','hit_internal_TTFT_app_ms')}
    save(OUT/'TIMING_PC_ONLY.json',dict(status='DESCRIPTIVE_25_DIFFERENT_INPUTS_ONE_R0_HIT_PAIR_EACH_NOT_REPEATED_BENCHMARK',
        units='ms',timing=timing,session_setup_and_initial_warm_outside_clock=True,
        new_PL_manager_periodic_health_and_request_END_journal_included=False,
        harness='FROZEN_OLD_CPU_ONLY_SESSION_MEASUREMENT',p95=None,Board_latency_s=None,Board_CMA=None,production_SLA=False))
    save(OUT/'COMMANDS.json',dict(observation_source='Actual outer tool results; original native stdout.jsonl and per-request records are retained. Outer CLI text was not separately redirected.',
        commands=[dict(command=['python3','-B','platform/qwen35/a12/promptcopy_candidate.py','prepare'],exit_code=0,candidate=CANDIDATE),
            dict(command=['python3','-B','platform/qwen35/a12/promptcopy_candidate.py','run'],exit_code=0,candidate=CANDIDATE),
            dict(command=['python3','-B','platform/qwen35/a12/promptcopy_audit.py'],exit_code=0)],
        earlier_failures=['PREPARE_FAILURE-v1.json','RUN_WITHOUT_PREPARED_FAILURE-v1.json'],BOARD='NOT_TESTED'))
    completion=read(PARENT/'COMPLETION_AUDIT.json')
    for row in completion['requirements']:
        if row['id']=='SHORT_PROMPT':row.update(offline='NEW_FACTS_ONLY_CANDIDATE_25_OF_25_ORIGINAL_FINITE_CHECKER_50_CPU_GENERATIONS_AND_7_ZERO_MODEL_POLICY_CASES',
            original_variants='20_OF_25_20_OF_25_21_OF_25_REMAIN_NOT_ACCEPTED',evidence=HANDOFF,
            default_adopted=False,actual_PL_protocol_binding='NOT_TESTED',medical_review='NOT_PERFORMED',BOARD='NOT_TESTED')
    remaining=[dict(id='NEW_PROMPT_PRIVATE_ROUTE',BOARD_required=False,status='UNRESOLVED_OFFLINE',
        work='Bind the independently accepted facts-only prompt and its newly frozen identity/34-token prefix to the actual private-protocol model manager in isolated PC windows; verify actual math, request budgets, fresh-health/delivery fences and all unchanged content/failure checks. Keep the ordinary resource baseline unchanged.'),
        dict(id='SERVICE_ROUTING',BOARD_required=False,status='SEPARATE_IMPLEMENTATION_REMAINS',
        work='Prepare bounded resident interactive application routing and per-request lifecycle using the accepted private protocol. Do not label a three-request acceptance window as unlimited SERVICE, and do not enable Board operation before separate acceptance.')]
    remaining += [r for r in completion['remaining'] if r['BOARD_required']]
    completion.update(previous_turn_classification='progress',current_turn_classification='progress',whole_goal_achieved=False,goal_status='active',
        remaining=remaining,next_safe_action=remaining[0]['work'],all_offline_work_done=False)
    save(OUT/'COMPLETION_AUDIT.json',completion);save(OUT/'NEXT_WORK.json',dict(goal_status='active',remaining=remaining,automatic_Board_action=False))
    activation=dict(BOARD='NOT_TESTED',production_enabled=False,default_prompt_changed=False,ordinary_probe_replaced=False,
        actual_PL_results_consumed=False,ARM_execution='NOT_EXECUTED',medical_review='NOT_PERFORMED',
        candidate_finite_content='PASS_FIXED_25_INPUTS_ONLY',SERVICE_ready=False,Board_latency_saving_s=None,Board_CMA=None)
    save(OUT/'ACTIVATION.json',activation)
    files={};here=ROOT/'platform/qwen35/a12'
    for p in sorted(here.iterdir()):
        if p.is_file() and p.name.startswith('promptcopy_'):files['source/'+p.name]=p.read_bytes()
    files['source/short_prompt_offline.py']=(here/'short_prompt_offline.py').read_bytes()
    for p in sorted(folder.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:files['candidate/'+p.relative_to(folder).as_posix()]=p.read_bytes()
    for name in ('PLAN.json','INDEPENDENT_AUDIT.json','RUNNER_REUSE.json','RUNTIME_REUSE.json','TIMING_PC_ONLY.json','ACTIVATION.json'):
        files['review/'+name]=(OUT/name).read_bytes()
    files['README.txt']=('ISOLATED CPU PROMPT REVIEW ONLY. NOT STANDALONE OR BOARD-AUTHORIZED.\n'
        'Facts-only prompt retains original question interpretation in the frozen planner/Session and request identity; it transmits only selected approved fact clauses to the model.\n'
        'All 25 fixed inputs and 7 policy routes retained. Fifty actual CPU R0/hit generations passed original finite content/EOS checks; no template fallback counted as model success.\n'
        'Finite grammar checks are not medical/teacher review. Default application and original ordinary Board resource bundle unchanged.\n'
        'New identity and actual 34-token prefix; old snapshot rejected. No model/weights/sidecars/bitstream, install/recovery or Board execution script.\n'
        'The current private PL manager and resident application integration remain separate unfinished work. CPU timings exclude that chain and are not Board predictions.\n').encode()
    archive=OUT/'facts-only-prompt-PC-review-v1.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    members=[dict(name=n,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in sorted(files.items())]
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(files)
        for row in members:assert hashlib.sha256(z.read(row['name'])).hexdigest()==row['sha256']
    save(OUT/'PACKAGE_REVIEW.json',dict(status='PASS_REVIEW_ZIP_ALL_MEMBERS',archive=pin(archive),members=members,standalone=False,deployable=False))
    report=f'''# A12 事实句短提示词：无板验证（2026-10-26）

新增独立facts-only候选，**25/25固定模型输入通过原有限语法内容/EOS检查，7项策略输入保持零模型调用**。每项实际执行R0/hit，共50次真实CPU模型生成，两个worker正常exit0。此前三个候选仍为20/25、20/25、21/25并保持NOT_ACCEPTED，原失败不改写。

## 改动与验证边界

原planner/Session仍接收原学生问题、选择已核对事实并保留请求身份；生成提示词只传这些完整事实句，避免再次让模型解释问题或跟随错误时间暗示。病例、问题、事实值/单位/肯否/未知、路由、有限检查器、24-token输出限额及贪心采样均不变。只修改隔离application副本的prompt_messages，其他AST与原件相同，默认应用没有启用。

模型原文、输出token、EOS与原生stdout逐项核对，重算原checker和应用answer_source/final_check。全部50次均为MODEL，未用模板兜底计成功。R0/hit输出、末位置logits、状态摘要及清理一致；状态仅核对runtime报告的SHA摘要，没有导出/独立读取完整中间值。独立审计的8项反例确认原文/检查/EOS/来源篡改被拒绝，原有改写、漏尺度、把未知说成已知和问题回声仍不通过。

新公共前缀实际34 token，全输入48～55，命中后新算14～21；25/25均不超过24。旧16～24区间内9项，其余16项少于16，并未抬长它们来满足区间。新前缀通过实际token一致边界与全部25组R0/hit数值对照；旧70-token前缀和旧binding实际拒绝。快照仍约21.6MB，不能称零内存成本；无全位置logits、原始状态转储或历史诊断重读，没有板端CMA结论。

准备阶段曾因在两句间加换行被原checker拒绝，保留facts-only-01和原源码；改用原完整句号直接连接，不改checker。随后一次误调用run因缺PREPARED而拒绝，没有启动模型，失败记录保留。最终facts-only-02及独立审计通过。

## 耗时与尚未完成项

旧CPU专用验证器、25个不同固定输入各一组描述性样本：完整核验答案R0中位{timing['R0_complete_app_ms']['median']/1000:.3f}s，hit中位{timing['hit_complete_app_ms']['median']/1000:.3f}s；hit范围{timing['hit_complete_app_ms']['min']/1000:.3f}～{timing['hit_complete_app_ms']['max']/1000:.3f}s。会话创建和首次warm在时钟外，**没有纳入新PL管理器周期安全检查及请求END持久化链**；不能据此预测A53/PL、生产端到端或稳定p95。板端时延收益仍null。

下一项无板工作是把新提示词/身份/前缀接入真实私有协议模型管理链，再做常驻交互应用接线。该候选通过固定有限语法样本不代表医学/教师审核、私有PL管理链或最终SERVICE已验收。普通资源探测包保持原SHA `acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`，将来仍先用它取得原严格基线。

审阅包`{archive.relative_to(ROOT).as_posix()}`，SHA `{sha(archive)}`，全部成员CRC/SHA回读通过；依赖现有模型/native/math，不是独立部署包，不含权重、sidecar、位流或上板执行入口。

历史契约保护和新版配置均exit0；旧数学/默认应用/父阶段源码证据、168个父包文件及5公共契约重新核对不变。未连接板卡、未恢复/释放、未推送；原安全门槛及Board故障状态保留。复杂设计、生成链和证据验收未委派DeepSeek，实际模型/effort设置工具不可核实，记unknown。目标继续active。
'''
    with (ROOT/HANDOFF).open('x',encoding='utf-8') as f:f.write(report)
    for name in DOCS:shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.at-finalization'))
    current=read(ROOT/'docs/PROJECT_STATUS.json');assert KEY not in current;final=dict(current)
    final[KEY]=dict(activation,status='FACTS_ONLY_CANDIDATE_PC_25_OF_25_FINITE_CHECKER_PASSED',evidence=HANDOFF,
        fixed_model_inputs=25,actual_CPU_generations=50,policy_inputs=7,prefix_tokens=34,new_tokens=[14,21],whole_goal_achieved=False,goal_status='active')
    (ROOT/'docs/PROJECT_STATUS.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    text='独立facts-only短提示词25/25固定输入原checker/EOS通过、50次实际CPU R0/hit、7策略零模型及8审计反例通过；新前缀34 token，新算14～21，旧snapshot拒绝。原默认/普通资源包及三旧候选失败保留。有限语法非医学审核；私有PL管理链绑定和SERVICE接线仍待做，Board未测、目标active。'
    for name in DOCS[1:]:
        with (ROOT/'docs'/name).open('a',encoding='utf-8') as f:f.write('\n\n## A12事实句短提示词无板验证（2026-10-26）\n\n'+text+' 见 `'+HANDOFF+'`。\n')
    assert {k:v for k,v in read(ROOT/'docs/PROJECT_STATUS.json').items() if k!=KEY}==current
    for name in DOCS[1:]:assert (ROOT/'docs'/name).read_bytes().startswith((OUT/(name+'.at-finalization')).read_bytes())
    save(OUT/'PRESERVATION.json',dict(status='PASS',old_source_pins=old_sources,baseline_files=len(baseline['files']),
        other_status_entries_exact=len(current),original_parent_files=len(original['parent_files']),contracts=len(original['contract_files']),
        original_probe_sha256=sha(probe/'bundle-v2.zip'),default_application_unchanged=True,old_prompt_failures_unchanged=True,board_contacted=False,pushed=False))
    source=[pin(p) for p in sorted(here.iterdir()) if p.is_file() and p.name.startswith('promptcopy_')]
    evidence=[pin(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('FINAL_REVIEW.json','TERMINAL_VERIFICATION.json') and '__pycache__' not in p.parts]
    governance=[pin(ROOT/'docs'/name) for name in DOCS]+[pin(ROOT/HANDOFF)]
    save(OUT/'FINAL_REVIEW.json',dict(status='PASS_FACTS_ONLY_FIXED_COHORT_PC_SCOPE',source=source,evidence=evidence,governance=governance,
        BOARD='NOT_TESTED',production_enabled=False,whole_goal_achieved=False,all_offline_work_done=False,goal_status='active'))
    for row in source+evidence+governance:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
    save(OUT/'TERMINAL_VERIFICATION.json',dict(status='PASS_ALL_LISTED_CURRENT_BYTES',pins_verified=len(source+evidence+governance),
        final_review_SHA256=sha(OUT/'FINAL_REVIEW.json'),whole_goal_achieved=False,goal_status='active',BOARD='NOT_TESTED'))
    print('PASS_ALL_LISTED_CURRENT_BYTES',len(source+evidence+governance))
if __name__=='__main__':main()
