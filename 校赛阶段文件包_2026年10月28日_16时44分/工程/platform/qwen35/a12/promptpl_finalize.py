"""Seal current-code private-prompt CPU tests; Board and resident service stay off."""
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import zipfile
from promptpl_evidence import ROOT,OUT,PARENT,MODE,DOCS,read,save,sha,pin

KEY='a12_facts_only_private_route_pc_20261026'
HANDOFF='docs/handoffs/A_A12_FACTS_ONLY_PRIVATE_ROUTE_PC_20261026.md'

def local(path):
    s=str(path).replace('\\','/')
    return ROOT/s[len('C:/Patientqwen/'):] if s.startswith('C:/Patientqwen/') else Path(path)

def main():
    artifact=read(OUT/'ARTIFACT_REVIEW.json');assert artifact['current_normal_windows']==31 and artifact['targeted_fault_windows']==8
    baseline=read(OUT/'BASELINE.json')
    for r in baseline['files']:assert sha(ROOT/r['path'])==r['sha256']
    older=read(PARENT/'PRESERVATION.json')['old_source_pins']+read(PARENT/'FINAL_REVIEW.json')['source']
    for r in older:assert sha(ROOT/r['path'])==r['sha256']
    for r in read(PARENT/'PLAN.json')['protected_default_sources']:assert sha(ROOT/r['path'])==r['sha256']
    prior_failures=ROOT/'evidence/model_pl_A/20261025-request-journal-v2/short-prompt-review-01'
    for r in read(prior_failures/'SOURCE_FILES.json'):assert sha(ROOT/r['path'])==r['sha256']
    for r in artifact['runtime_artifacts']+[artifact['quantization_object']]:assert sha(r['path'])==r['sha256']
    probe=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1';old=read(probe/'BASELINE.json')
    for r in old['parent_files']:assert sha(local(old['parent_bundle'])/r['path'])==r['sha256']
    for r in old['contract_files']:assert sha(local(r['path']))==r['sha256']
    assert sha(probe/'bundle-v2.zip')=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    for label,script in [('HISTORICAL_CONTRACT_GUARD','scripts/release/check_contracts.py'),('QWEN35_CONFIG_GUARD','scripts/release/qwen35_config.py')]:
        cmd=[sys.executable,script];r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        save(OUT/(label+'.json'),dict(command=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));assert r.returncode==0
    normal=read(OUT/'cohort02-AUDIT.json')['windows'];strict=read(OUT/'strict01-AUDIT.json')['windows'];timing={}
    for name,rows in (('cap72_all_25',normal),('cap1_six_representatives',strict)):
        timing[name]={}
        for mode in ('app_R0','app_hit'):
            values=[next(a for a in row['answers'] if a['id']==mode)['send_to_verified_answer_s'] for row in rows]
            timing[name][mode]=dict(min=min(values),median=statistics.median(values),max=max(values))
    save(OUT/'TIMING_PC_ONLY.json',dict(scope='SEND_TO_VERIFIED_RESULT_INCLUDING_CONTENT_END_RECEIPT_FINAL_FENCE',units='seconds',timing=timing,
        repeated_same_input_distribution=False,cohort_pair_order='ALL_CAP72_THEN_SIX_CAP1_NOT_RANDOMIZED',
        actual_input_routing_and_service_admission_included=False,load_and_warm_outside_request_clock=True,
        p95=None,BOARD='NOT_TESTED',Board_CMA=None,Board_latency_saving_s=None,production_SLA=False))
    remaining=read(PARENT/'NEXT_WORK.json')['remaining']
    remaining=[r for r in remaining if r['id']!='NEW_PROMPT_PRIVATE_ROUTE']
    for r in remaining:
        if r['id']=='SERVICE_ROUTING':r['work']='Implement docs/A12_BOUNDED_RESIDENT_SERVICE_DESIGN_20261026.md: bounded resident interactive application routing with the now-validated facts-only private protocol; prepare model/prefix before readiness, retain original total/deadline/resource caps, content/END/receipt/fresh delivery gates and failure quarantine. Prepare the corresponding typed Board workload adapter separately, without executing it. Three fixed acceptance requests do not provide continuous SERVICE.'
    completion=read(PARENT/'COMPLETION_AUDIT.json')
    for r in completion['requirements']:
        if r['id']=='SHORT_PROMPT':r.update(actual_PL_protocol_binding='ACTUAL_CPU_PRIVATE_PROTOCOL_25_COHORTS_PLUS_SIX_STRICT_WINDOWS_VERIFIED_NO_REAL_PL_RESULTS',latest_evidence=HANDOFF)
    completion['requirements'].append(dict(id='FACTS_ONLY_PRIVATE_ROUTE',offline='CURRENT_CODE_25_CAP72_AND_SIX_CAP1_WINDOWS_EIGHT_TARGETED_FAULTS',evidence=HANDOFF,
        lifecycle_freshness='AFTER_DURABLE_LEGACY_RECORD_250MS_AND_FAULT_LATCH_UNCHANGED',
        CPU_math='EXISTING_NATIVE_AND_ADAPTER_REAL_W4A8_MATH',actual_PL_results_consumed=False,BOARD='NOT_TESTED'))
    completion.update(previous_turn_classification='progress',current_turn_classification='progress',whole_goal_achieved=False,all_offline_work_done=False,
        goal_status='active',remaining=remaining,next_safe_action=remaining[0]['work'])
    save(OUT/'COMPLETION_AUDIT.json',completion);save(OUT/'NEXT_WORK.json',dict(goal_status='active',remaining=remaining,automatic_Board_action=False))
    activation=dict(BOARD='NOT_TESTED',ARM_execution='NOT_EXECUTED',production_enabled=False,SERVICE_ready=False,
        default_prompt_changed=False,ordinary_probe_replaced=False,current_private_prompt_provider='CPU_ONLY_TYPED_EXPERIMENT',
        new_prompt_Board_workload_adapter='NOT_IMPLEMENTED',actual_PL_results_consumed=False,release_authority=False,
        Board_CMA=None,Board_latency_saving_s=None,medical_review='NOT_PERFORMED')
    save(OUT/'ACTIVATION.json',activation)
    files={};here=ROOT/'platform/qwen35/a12'
    for p in sorted(here.iterdir()):
        if p.is_file() and p.name.startswith(('promptpl_','test_promptpl_')):files['source/'+p.name]=p.read_bytes()
    for relative in ('cohorts','cohort02','strict01'):
        for p in sorted((OUT/relative).rglob('*')):
            if p.is_file():files['evidence/'+p.relative_to(OUT).as_posix()]=p.read_bytes()
    for r in read(OUT/'faults01-SUITE.json')['windows']:
        for p in sorted((OUT/r['folder']).rglob('*')):
            if p.is_file():files['evidence/'+p.relative_to(OUT).as_posix()]=p.read_bytes()
    for name in ('COHORTS.json','ARTIFACT_REVIEW.json','FINAL_DERIVATION.json','WORKLOAD_POLICY_TEST.json','LIFECYCLE_FENCE_TEST.json',
        'STDOUT_BOUND_COUNTEREXAMPLE.json','LIFECYCLE_STALE_FAILURE-v1.json','TIMING_PC_ONLY.json','ACTIVATION.json',
        'cohort02-AUDIT.json','strict01-AUDIT.json','faults01-AUDIT.json'):
        files['review/'+name]=(OUT/name).read_bytes()
    files['README.txt']=('OFFLINE PRIVATE-PROMPT CPU REVIEW ONLY. NOT STANDALONE OR BOARD AUTHORIZATION.\n'
        'The existing actual native/CPU adapter and original request, source, health, budget, graph-copy, END/receipt/fresh-delivery gates are exercised.\n'
        'All 25 facts-only cohorts passed cap72; six representative cohorts passed cap1. Eight targeted fault windows withhold answers.\n'
        'Startup stale legacy-ticket failure is retained. Lifecycle-only fresh ticket now follows durable record, with unchanged 250ms bound and fault latch.\n'
        'The three-request acceptance window is not resident interactive SERVICE. New-prompt typed Board adapter remains unfinished and no ARM was executed.\n'
        'No model/weights/sidecars/bitstream, install/recovery or Board execution scripts. Original ordinary probe remains first later Board baseline.\n'
        'CPU timings start at native send and omit real input routing, initial model/prefix readiness and any Board performance evidence.\n').encode()
    archive=OUT/'facts-only-private-PC-review-v1.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    members=[dict(name=n,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in sorted(files.items())]
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(files)
        for r in members:assert hashlib.sha256(z.read(r['name'])).hexdigest()==r['sha256']
    save(OUT/'PACKAGE_REVIEW.json',dict(status='PASS_ALL_REVIEW_PACKAGE_MEMBERS',archive=pin(archive),members=members,standalone=False,deployable=False))
    hit=timing['cap72_all_25']['app_hit'];stream_counter=read(OUT/'STDOUT_BOUND_COUNTEREXAMPLE.json')
    report=f'''# A12 事实句短提示词接入私有协议：无板验证（2026-10-26）

当前代码完成25个固定输入的微批窗口和6个代表输入的逐次许可窗口，共31窗、62份模型回答及31次warm；8个定向故障窗均拒绝交付。它们使用真实CPU数学和原生私有Route/本地预算/图拷贝检查，设备/内存健康来源仍为明确PC夹具。没有真实PL结果、Board许可或物理释放结论。

## 接线与安全保持

新提示词仍由原有限checker/事实/路由约束，默认应用及原普通包不改。每窗新冻结request/前缀身份：34-token公共前缀、48～55全输入、14～21新token及24-token输出上限。管理器依据冻结请求动态算prefill尾块/最大decode预算，保留逐提交启动前本地检查、5000总上限、72权重、期限、请求顺序和原健康门槛；没有重置预算或自动重放。

源码14处可逆替换覆盖固定输入选择、prefix/output核算、stdout有界容量、关闭累计实际计数和生命周期新鲜检查位置；原native/adapter/数学DSO及量化对象按SHA复用，公共ABI/契约和Board候选原件不改。stdout改为2×24+5=53个消息上限，单行128KiB、总1MiB不变；实际{stream_counter['cohort_id']}流有{stream_counter['actual_stream_packets']}条，旧解析器拒绝/新解析器完整通过的PC回放反例保留。反例夹具最初误选27条的V08，修为从全25项中选实际最长流；失败记录保留，没有重跑或改写模型。

## 发现的阻碍与修复

cohort01前20窗正常，V04在第38个权重装载许可记录之后票据过期，实际计算claims0、进程exit2，无答案交付，撤销页/DIRTY保留。现场没有单独计量fsync与调度延迟，不能把停顿归因于CMA；真实HealthFence线程加阻塞journal代理复现了先取票据再等持久化会过期的机制。

只将生命周期许可的最终fresh fence移到持久记录之后；250ms上限、原故障锁存和在途语义不变，不复用旧票据。阻塞期间健康故障依然拒绝回复。请求/GRANT/END的原关口保持；end_slow仍因过期票据拒绝交付。旧20窗与V04失败均保留，修复后的cohort02才是25项当前代码证明。

独立审计初版把已经是256-bit摘要的Source epoch再次哈希，发生拒绝；修为原生slot实际存储的原epoch编码直接比较，没有改变来源或门槛。旧审计源码和失败记录保留。

## 当前证据

- cohort02：全部25固定输入各R0/warm/hit，token/text/EOS、末位置logits和runtime状态/前缀SHA摘要与上轮CPU基线一致；END、回执和最终fresh fence逐一核对，正常native exit0且独立持有pidfd已终止、只读页已撤销且无unknown/active。
- strict01：DEV-001/004/005/011/012及V08共6项逐次许可，覆盖新token尾块、最大/最小、尺度、未知及双事实；未把6项称作25项严格模式全测。
- faults01：BEGIN/GRANT/END/receipt fsync失败、END慢写、请求摘要篡改、同UUID节点重建、图拷贝损坏；核对实际claims/CPU启动与核验/图拷贝、具体失败原因、零可交付结果及DIRTY/撤销保留。失败END或回执文件存在不作为成功交付证明。
- 13项输入/前缀/预算拒绝、旧stdout界限反例、生命周期先持久后fresh及期间故障锁存测试通过。原CMA/内存阈值没有板测或放宽；完整中间数值/硬件故障仍未测试。

## 应答时间和后续

当前私有链微批下，25种输入各一次的hit“发送到完整核验结果”中位{hit['median']:.3f}s，范围{hit['min']:.3f}～{hit['max']:.3f}s，已包括内容、END、回执和最终fresh检查。没有包含实时应用路由、会话建立和初始权重/warm；不是完整输入端到端、重复分布/p95、Board预测或SLA。逐次模式只有6个代表输入，顺序样本不作严谨因果性能估计。

下一步仍需常驻交互应用接线及新短提示词的typed Board workload准备，保持原总预算/期限和故障隔离，不把三请求窗改称无限SERVICE。模型与公共前缀应在ready前准备，实际BOARD及投入使用前的数值/生命周期/长期稳定/医学审核另验。无板接线规格见docs/A12_BOUNDED_RESIDENT_SERVICE_DESIGN_20261026.md；它目前仅为设计。

审阅包`{archive.relative_to(ROOT).as_posix()}`，SHA `{sha(archive)}`，全部CRC/成员SHA回读通过；依赖冻结仓库与原模型/native/math，不含模型/sidecar/bitstream、安装恢复或上板执行脚本。原普通资源包SHA仍为`acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`，将来首轮基线不替换。

历史契约保护和新版配置检查exit0，旧DRAFT/BOARD NOT_TESTED保持；父阶段源/证据、168父包文件及5契约重新核对。未连接板卡、未恢复/释放/推送。核心逻辑和证据未委派DeepSeek，实际模型/effort设置工具不能核实，记unknown。总目标active，不能称只剩上板。
'''
    with (ROOT/HANDOFF).open('x',encoding='utf-8') as f:f.write(report)
    for name in DOCS:shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.at-finalization'))
    current=read(ROOT/'docs/PROJECT_STATUS.json');assert KEY not in current;final=dict(current)
    final[KEY]=dict(activation,status='FACTS_ONLY_PRIVATE_CPU_PROTOCOL_FIXED_COHORT_VALIDATED',evidence=HANDOFF,
        current_normal_windows=31,targeted_fault_windows=8,goal_status='active',whole_goal_achieved=False)
    (ROOT/'docs/PROJECT_STATUS.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    text='事实句短提示词接入实际CPU私有协议，当前25微批窗+6严格代表窗、8定向故障、13策略拒绝及独立审计通过。动态核算34-token前缀/24-token输出，原5000及健康门槛保留。生命周期持久记录后取最终fresh票据，旧V04启动失败留档；不是Board或SERVICE验收，常驻交互和新提示词Board适配仍待做，目标active。'
    for name in DOCS[1:]:
        with (ROOT/'docs'/name).open('a',encoding='utf-8') as f:f.write('\n\n## A12短提示词私有协议无板验证（2026-10-26）\n\n'+text+' 见 `'+HANDOFF+'`。\n')
    assert {k:v for k,v in read(ROOT/'docs/PROJECT_STATUS.json').items() if k!=KEY}==current
    for name in DOCS[1:]:assert (ROOT/'docs'/name).read_bytes().startswith((OUT/(name+'.at-finalization')).read_bytes())
    save(OUT/'PRESERVATION.json',dict(status='PASS',old_source_pins=older,baseline_files=len(baseline['files']),other_status_entries_exact=len(current),
        original_parent_files=len(old['parent_files']),contracts=len(old['contract_files']),original_probe_sha256=sha(probe/'bundle-v2.zip'),
        old_failures_preserved=True,board_contacted=False,pushed=False))
    source=[pin(p) for p in sorted(here.iterdir()) if p.is_file() and p.name.startswith(('promptpl_','test_promptpl_'))]
    evidence=[pin(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('FINAL_REVIEW.json','TERMINAL_VERIFICATION.json') and '__pycache__' not in p.parts]
    governance=[pin(ROOT/'docs'/name) for name in DOCS]+[pin(ROOT/HANDOFF),pin(ROOT/'docs/A12_BOUNDED_RESIDENT_SERVICE_DESIGN_20261026.md')]
    save(OUT/'FINAL_REVIEW.json',dict(status='PASS_FIXED_FACTS_ONLY_PRIVATE_CPU_PROTOCOL_SCOPE',source=source,evidence=evidence,governance=governance,
        BOARD='NOT_TESTED',whole_goal_achieved=False,all_offline_work_done=False,goal_status='active'))
    for r in source+evidence+governance:assert sha(ROOT/r['path'])==r['sha256'] and (ROOT/r['path']).stat().st_size==r['bytes']
    save(OUT/'TERMINAL_VERIFICATION.json',dict(status='PASS_ALL_LISTED_CURRENT_BYTES',pins_verified=len(source+evidence+governance),
        final_review_SHA256=sha(OUT/'FINAL_REVIEW.json'),whole_goal_achieved=False,goal_status='active',BOARD='NOT_TESTED'))
    print('PASS_ALL_LISTED_CURRENT_BYTES',len(source+evidence+governance))
if __name__=='__main__':main()
