"""Verify actual required receipts, finite inputs, deployed sources, then write reports."""
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys

ROOT=Path(__file__).resolve().parents[3]
EV=Path(__file__).resolve().parent
RELEASE=ROOT/'release/a12_realtime_model_draft_20261027_v1'
PACKAGE=RELEASE/'realtime34-threads3-out32'
WEB=ROOT/'platform/qwen35/web'
sys.path.insert(0,str(WEB));sys.path.insert(0,str(WEB/'vendor/web_gateway/src'))
from answer_cache_build import enumerate_plans
from compact_fact_prompt import prompt_messages,policy_sha256
from realtime_draft import fact_copy_draft,STRATEGY
from patient_web.reference.checking import check
from jinja2.sandbox import ImmutableSandboxedEnvironment
from continuous_sessions import question_reserve
from fast_response_prepare_support import verify_package


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def stats(xs):return dict(min=min(xs),median=statistics.median(xs),max=max(xs),samples=len(xs))
def prepend(path,heading,body):
    path=Path(path);old=path.read_bytes()
    assert heading.encode('utf-8') not in old,path
    path.write_bytes((heading+'\n\n'+body.strip()+'\n\n').encode('utf-8')+old)


names=['base-contracts','base-config','build-pc-v3-command','build-arm-a53-env-command',
       'pairs198-t2-32-command','pairs198-final-command','baseline-serve01-command','baseline-browser01-command',
       'realtime-serve01-command','realtime-browser01-command','browser-ab01-command','package-prepare-command',
       'package-preflight-a53-command','rebind-a53-02-command','actual-miss-command','packaged-serve01-command','packaged-browser01-command',
       'tests-final-command','browser-regression-command']
receipts={name:read(EV/name/'COMMAND.json') for name in names}
assert all(row['exit_code']==0 for row in receipts.values())
assert read(EV/'pairs198-v2-command/COMMAND.json')['exit_code']==1
base=read(EV/'pairs198-t2-32/RESULT.json');final=read(EV/'pairs198-final/RESULT.json')
assert base['total']==final['total']==198 and base['accepted']==final['accepted']==198
assert final['real_model_requests']==408 and final['wrong_draft_replays']==6 and final['extended_reject_and_cancel_checks']
assert final['worker_exit']==base['worker_exit']==0 and final['answer_cache_reads']==0
pc=read(EV/'BUILD-PC-v3.json');arm=read(EV/'BUILD-ARM-v3-a53.json')
assert sha(pc['binary'])==pc['sha256']==final['binary_sha256']
assert sha(arm['binary'])==arm['sha256']
assert int.from_bytes(Path(arm['binary']).read_bytes()[18:20],'little')==183
flags=Path(arm['binary']).parent/'CMakeFiles/qwen35-a12.dir/flags.make'
assert '-mcpu=cortex-a53' in flags.read_text() and '-march=native' not in flags.read_text()
shutil.copyfile(flags,EV/'A53_FLAGS.make')
source=read(EV/'SOURCE-v3.json')
for row in source['files']:
    assert sha(EV/'source-v3'/row['name'])==row['sha256']
    if row['name']!='main.cpp':assert row['sha256']==row['base_sha256']

# The current host helpers must still produce the exact inputs that were actually run.
template=ImmutableSandboxedEnvironment().from_string((PACKAGE/'continuous/bundle/control/chat_template.jinja').read_text(encoding='utf-8'))
proofs=[]
for i,(case,plan) in enumerate(enumerate_plans(),1):
    a=read(EV/'pairs198-final/proof'/f'pair-{i:03d}-serial.json')
    b=read(EV/'pairs198-final/proof'/f'pair-{i:03d}-draft.json')
    messages=prompt_messages(plan,'')
    prompt=template.render(messages=messages,add_generation_prompt=True,enable_thinking=False)
    assert a['request']['prompt']==b['request']['prompt']==prompt
    assert b['request']['draft_text']==fact_copy_draft(messages)
    assert a['result']['output_tokens']==b['result']['output_tokens']
    assert a['result']['text']==b['result']['text']
    for item in (a,b):
        r=item['result']
        assert r['status']=='OK' and r['eos'] and not r['teacher_forced']
        assert r['bridge']['execution_kind']=='CPU_REFERENCE' and r['state_position_after_clear']==-1 and r['state_cleared_before_response']
        assert check(plan,r['text'])['status']=='pass'
        assert r['request_profile']['cpu_counters']['run_count_delta']>0
    spec=b['result']['speculative_decoding']
    assert spec['accepted'] and spec['target_eos_verified'] and not spec['answer_cache_used'] and not spec['forced_output']
    assert spec['target_greedy_tokens'][:-1]==spec['proposed_tokens']==b['result']['output_tokens']
    assert spec['argmax_checks']==len(b['result']['output_tokens'])+1
    proofs.append(dict(id=i,case_id=case.case_id,facts=plan.required_fact_ids,
                       serial_sha256=sha(EV/'pairs198-final/proof'/f'pair-{i:03d}-serial.json'),
                       draft_sha256=sha(EV/'pairs198-final/proof'/f'pair-{i:03d}-draft.json')))
for label in ('late-reject','missing-eos','reject-R0'):
    r=read(EV/'pairs198-final/proof'/(label+'.json'))['result']
    assert r['speculative_decoding']['fallback_full_prompt_replayed'] and not r['speculative_decoding']['accepted'] and r['eos']
r=read(EV/'pairs198-final/proof/cancel-during-verification.json')['result']
assert r['status']=='CANCELLED' and r['state_cleared_before_response'] and r['state_position_after_clear']==-1
recovery=read(EV/'pairs198-final/proof/after-cancel.json')['result']
assert recovery['output_tokens']==read(EV/'pairs198-final/proof/pair-001-serial.json')['result']['output_tokens']
save(EV/'FINITE_INPUT_AND_RESULT_PROOFS.json',dict(status='PASS_CURRENT_INPUTS_MATCH_ACTUAL_198_TARGET_RUNS',rows=proofs))

ab=read(EV/'BROWSER_AB.json');assert ab['total']==25 and ab['answer_cache_hits']==0 and ab['draft_accepted']==25
assert ab['original_checker_equivalent_forms'] and all(r['reduction_ms']>0 for r in ab['rows'])
for name in ('baseline-serve01','realtime-serve01','packaged-serve01'):
    r=read(EV/name/'RESULT.json')
    assert r['native_count']==25 and r['worker_exit']==0 and r['cache'] is None and r['HTTP_layer_retained_worker']
packaged=read(EV/'packaged-browser01/RESULT.json');assert packaged['questions']==25 and packaged['browser_exit']==0
for row in packaged['rows']:
    t=row['turn'];assert t['answer_source']=='MODEL' and t['actual_backend']=='CPU_REFERENCE' and t['delivery_receipt']['model_called']
    assert t['timing']['native_speculative_decoding']['target_eos_verified'] and t['delivery_receipt']['validation_status']=='pass'
package_ms=stats([r['timing']['submit_to_paint_ms'] for r in packaged['rows']])
miss=read(EV/'actual-miss/RESULT.json');assert miss['actual_model_calls']==1 and miss['worker_exit']==0
assert len(miss['policy_items'])==7 and miss['same_session_score']==20 and miss['archived_cache_sessions']==10 and miss['retained_in_memory']==8
actual=read(EV/'actual-miss/HIT_MISS.json')[0]
assert actual['turn']['answer_source']=='MODEL' and actual['response']['model_result']['speculative_decoding']['target_eos_verified']
assert actual['turn']['delivery_receipt']['model_called']
assert 'Ran 43 tests' in (EV/'tests-final-command/stderr.txt').read_text()
assert read(EV/'browser-regression/RESULT.json')['status']=='PASS_BROWSER_FIXTURES'
assert question_reserve(1024,34,32,draft_strategy=STRATEGY)==22320
verify_package(PACKAGE)
pins=[]
for kind in ('ordinary','continuous'):
    window=PACKAGE/kind
    for p in WEB.glob('*.py'):
        if p.name in ('fast_response_prepare.py','answer_cache_prepare.py','realtime_draft_prepare.py'):continue
        assert sha(window/p.name)==sha(p),p
    for name in ('native_pl.py','web_managed.py'):assert sha(window/name)==sha(ROOT/'system_qwen35/app'/name)
    assert sha(window/'bundle/bin/qwen35-a12')==arm['sha256']
    for p in (WEB/'vendor/web_gateway').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            assert sha(window/'web_gateway'/p.relative_to(WEB/'vendor/web_gateway'))==sha(p),p
for p in sorted([*WEB.glob('*.py'),*(WEB/'vendor/web_gateway').rglob('*'),
                 *(ROOT/'bench/qwen35/web').glob('*.py'),ROOT/'system_qwen35/app/native_pl.py',
                 ROOT/'system_qwen35/app/web_managed.py',ROOT/'platform/qwen35/a12/realtime_draft_derive.py']):
    if p.is_file() and '__pycache__' not in p.parts:pins.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
save(EV/'IMPLEMENTED_SOURCE_PINS.json',pins)
experiments={name:read(EV/name/'RESULT.json') for name in ('smoke01','smoke02','threads3-smoke','compact2-smoke','compact3-smoke','nospace-smoke')}
save(EV/'EXPERIMENT_SELECTION.json',dict(selected='v3 / 3 threads / allowed-compact-01 / 34 prefix / 32 output',
    selected_policy_sha256=policy_sha256(),summaries={n:{k:v for k,v in r.items() if k!='rows'} for n,r in experiments.items()},
    no_space_prompt_selected=False,no_space_rejection_reason='numeric spacing still differs: fallback raised worst native time to 2282ms'))
save(EV/'FAILURES.json',dict(preserved=True,required_unresolved_no_board_items=[],rows=[
    dict(attempt='naive literal draft',evidence='smoke01',cause='model adds spaces around ASCII numbers',resolution='single deterministic spacing rule over current input, all tokens still target-verified'),
    dict(attempt='pairs198-v2',evidence='pairs198-v2/proof/pair-039-serial.json',cause='old24 output bound cannot sample EOS after24 answer tokens',resolution='new continuous32 bound, 22320 budget; original failure retained'),
    dict(attempt='no-space prompt',evidence='nospace-smoke/RESULT.json',cause='one of11 drafts rejected; worst2282ms',resolution='not selected; deployed SYSTEM and34 prefix remain unchanged'),
    dict(attempt='initial ARM SDK flags',evidence='verify-report-command/stderr.txt',cause='SDK OEToolchainConfig FORCE-overrode CMAKE_CXX_FLAGS from environment',resolution='pass accepted A53 flags in subprocess CXXFLAGS/CFLAGS; actual flags.make checked, separate rebuild and package rebind; PC runtime unchanged')]))

reduction=(ab['serial_ms']['median']-ab['realtime_ms']['median'])/ab['serial_ms']['median']*100
summary=f'''# A12：缓存未命中实时模型优化，无板总结（2026-10-27，v1）

本次目标是每问必须实时运行模型时，尽快看到完整、原checker通过的回答。当前推荐候选是`realtime34-threads3-out32`。以下主要指标均为**开发机x86 CPU热服务**；没有用答案缓存命中速度代替实时模型性能，中性34-token KV前缀仍复用。

## 完整可用回答现在需要多久

同机真实Edge、真实HTTP/SSE，25个相同问题与病例，测量浏览器提交到完整核验答案DOM更新后两次animation frame：

| 指标 | 原实时模型网页 | 优化后实时模型网页 |
| --- | ---: | ---: |
| 最快 | {ab['serial_ms']['min']:.1f}ms | {ab['realtime_ms']['min']:.1f}ms |
| 中位 | {ab['serial_ms']['median']:.1f}ms | **{ab['realtime_ms']['median']:.1f}ms** |
| 最慢 | {ab['serial_ms']['max']:.1f}ms | {ab['realtime_ms']['max']:.1f}ms |
| 本轮真实模型请求 | 25 | 25 |
| 答案缓存命中 | 0 | 0 |

两组中位数相差{ab['serial_ms']['median']-ab['realtime_ms']['median']:.1f}ms，等待降低约{reduction:.1f}%；逐题配对减少时间的中位为{ab['reduction_ms']['median']:.1f}ms。{ab['within_1s']}/25低于1秒，仍有2题略高于1秒，不宣称全部达标。

实际部署副本另跑25题，中位{package_ms['median']:.1f}ms、最慢{package_ms['max']:.1f}ms，仍为23/25低于1秒；25次真实模型请求，答案缓存未加载。另在合法197条目录中移除一个条目的真实未命中流程通过，只调用模型1次，缓存命中及7项策略不新增模型调用。

原先已有875.0ms是上一轮25题开发机结果；本轮重新测得879.0ms作为前后对照。原实板27.854秒属于历史不同路径，不能与这里毫秒数据相减得出实板加速。新实板时延仍未测试。

## 如何提速且保持真正运行模型

1. 选用原checker已有、表示同一完整事实的短表达作为模型输入，策略`allowed-compact-01`，不新增/删改checker表达。{ab['wording_changed']}/25答案措辞改变；两组都由未改的原checker独立证明全部原必需事实，未省略单位、时间、肯否或未知。
2. 从本题输入事实构造草稿，真实目标模型以有界因果batch计算每个位置；只有所有token均等于目标贪心选择、且EOS也通过，才交付。草稿不是可直接交付的模板，不读取答案目录。每题来源仍MODEL，model_called=true，实际后端CPU_REFERENCE。
3. 若有任何不符，丢弃全部草稿状态，清空recurrent/conv/KV，恢复原中性前缀并重放完整prompt，再正常串行生成。保留原状态/Owner链，不对DeltaNet做未经验证的部分截断。
4. 开发机2/3线程比较后选3线程；中性SYSTEM、34-token前缀、1024上下文、physical_ubatch=8、模型/量化/HLS/公共算子ABI不变。A53最佳线程数和收益仍待实板验证。

“decode_calls=0”表示没有逐token的串行API循环，不能解释为没有运行模型。目标模型层、MLP及每个候选位置的logits都实际计算；CPU请求级运行增量为正，逐token选择及EOS回执保留。新网页来源与原MODEL_CACHE明确分开。

## 完整性、成本及验证

- 三病例、11事实、最多两事实，共198组。原表达2线程串行/草稿198组逐token一致；最终短表达3线程另跑198组逐token一致、EOS及原checker全部通过，198/198草稿被真实模型接受，无答案缓存读取。最终测试408个真实模型请求，包含控制、拒绝和取消测试，不能说成408个正常完成答案。
- 最终198组同输入底层串行中位{final['serial_ms']['median']:.1f}ms，草稿验证中位{final['draft_ms']['median']:.1f}ms，验证组最慢{final['draft_ms']['max']:.1f}ms。这是含双事实的底层组合数据，不是198组网页延迟；网页计时以上表为准。
- 发现旧24输出上限在3个双事实组合不能取得EOS；最小反例为SYN_CP_01的duration+severity，第39组。失败原件保留；新连续候选显式改32输出，不截短答案换速度。普通R0/warm/hit窗口仍原24。
- 连续每问保守预算22320次运行，显式覆盖一次验证及最坏完整串行重放；不是沿用旧10584预算。实际用量与保留额度分开。
- 6个错误草稿、后缀错误、缺EOS、无前缀R0拒绝、验证中取消及下一问恢复通过；43网页测试、15浏览器协议回归通过。同场20分、幂等、新病例、10场归档/8场内存保留正常。
- PC/ARM新二进制分别SHA `{pc['sha256']}` / `{arm['sha256']}`。ARM按既有2026.1SDK、`-mcpu=cortex-a53`交叉构建，不使用开发机`-march=native`；构建不代表板测。
- 基线/优化PC服务启动及加载/预热分别约{read(EV/'baseline-serve01/HTTP_READY.json')['startup_ready_s']:.2f}/{read(EV/'realtime-serve01/HTTP_READY.json')['startup_ready_s']:.2f}秒，未计入提交后时延。未测冷启动下直接输入、长期稳定性或总体p95。

要求不补空格的额外提示词试验没有入选：模型仍在数字旁补空格，11题有1题重放，最慢达2.282秒。保留该实验，未覆盖本次较快候选。

封包时发现SDK的OEToolchainConfig会从环境强制覆盖CMake参数，初次ARM构建未显式限定A53。已在构建子进程CXXFLAGS/CFLAGS中复用原A53参数并重建，实际flags.make核实`-mcpu=cortex-a53`。旧件/失败原样保留；仅更新ARM字节与绑定摘要，294份运行时文件和PC配置/二进制的字节保持一致。

## 交付与使用

入口：`release/a12_realtime_model_draft_20261027_v1/START_HERE.md`。总交付包标准命名为`KV260_Qwen35_A12_RealtimeModel_VerifiedDraft_NoBoard_20261027_v1.zip`，内含部署子包、工程源码/测试/实际证据子包和本总结；外层及内部均有SHA清单。

部署包continuous保留原已核验答案缓存；缓存的原生成策略仍是facts-only-02-verified-answers-v1，不冒充本轮短表达生成。短表达和实时贪心验证只在未命中后运行。PC服务`--mode realtime`明确不加载答案缓存；该模式用于上述性能验收。

先按包内START_HERE运行PC package检查；现有模型权重/依赖仍需本机环境提供。另获实板执行授权后才按包内入口新建独立Owner窗口；结束问诊仅冻结评分，停止整个服务需等待原完成/恢复/独立释放回执。回退使用旧独立包，不复用已消费授权。

证据根目录：`evidence/model_pl_A/20261027-realtime-miss-opt-v1/`。逐题数据BROWSER_AB.json/CSV、408请求原件pairs198-final/proof、真实未命中actual-miss、部署副本packaged-browser01及*-command命令/退出码均保留。模型权重、工具链、镜像、凭据及可重放计算授权不随包提供。

本轮未连接或部署板卡。新的BOARD可见时延、PL未命中真实提交/完成、CMA/功耗及Owner硬件恢复/独立释放为NOT_TESTED/null。未全局升级依赖、训练、改HLS/公共数学/ABI或展开无关安全审查。各复杂阶段推荐Sol/High；沿用此前已核实的聊天配置，单次实际执行参数仍unknown。
'''
summary_path=ROOT/'docs/A12_REALTIME_MODEL_MISS_NOBOARD_SUMMARY_20261027.md'
summary_path.write_text(summary,encoding='utf-8')
(EV/'REPORT.md').write_text(summary,encoding='utf-8')
(PACKAGE/'REPORT_PC.md').write_text(summary,encoding='utf-8')
(ROOT/'docs/handoffs/A_A12_REALTIME_MODEL_MISS_NOBOARD_20261027.md').write_text(
    '# A12 实时模型未命中优化交接\n\n'+
    f'最终候选realtime34-threads3-out32；真实浏览器25题中位879→618.3ms，23/25低于1秒；每题实际模型请求1、答案缓存命中0。\n'+
    '当前输入短表达+严格目标贪心验证，错草稿全清并重放。最终198组逐token/EOS/原checker通过，普通24、连续32/22320预算。\n'+
    'SOURCE-v3除main.cpp外保持旧源SHA，PC/ARM新二进制已构建；部署副本25题及正常退出0验证完成。\n'+
    '原24上限EOS失败与较慢no-space试验原件保留。未上板，板端时延/真实PL未命中/恢复释放/CMA功耗计数均NOT_TESTED/null。\n'+
    '完整报告docs/A12_REALTIME_MODEL_MISS_NOBOARD_SUMMARY_20261027.md；入口release/a12_realtime_model_draft_20261027_v1/START_HERE.md。\n',encoding='utf-8')
common='真实Edge同题25对，完整核验答案879.0→618.3ms中位，23/25低于1秒；两组各25次真实CPU模型，答案缓存命中0。短表达由原checker已有forms选择，目标模型逐token贪心及EOS验证，失败全清并重放。最终198组合与同输入串行逐token一致；43网页、15浏览器回归、真实197目录未命中/评分/归档及部署副本25题通过。普通24保持，新连续32/22320预算覆盖完整重放。新A53交叉构建完成；BOARD仍NOT_TESTED/null。'
prepend(ROOT/'docs/TEST_MATRIX.md','## 2026-10-27 A12 实时模型未命中优化',common+'\n证据：evidence/model_pl_A/20261027-realtime-miss-opt-v1/。')
prepend(ROOT/'docs/DESIGN_GAP.md','## 2026-10-27 A12 实时未命中P1收口',common+'\n旧24输出在3个组合缺EOS的反例保留；未追改旧25题通过范围。实板时延/PL真实未命中和Owner恢复释放仍需另授权执行。')
prepend(ROOT/'docs/DECISIONS.md','## 2026-10-27 A12：严格贪心草稿验证与短表达输入',common+'\n旧缓存保留原生成策略和来源；当前未命中输入策略独立为allowed-compact-01，中性SYSTEM/34前缀不变。No-space提示词实验因最慢2.282秒未入选。模型/量化/公共ABI/HLS不改，native二进制显式派生。')
prepend(ROOT/'docs/AI_ASSISTANCE.md','## 2026-10-27 A12 缓存未命中实时优化',common+'\n应用llama-cpp与speculative-decoding技能，只采用原理并读固定本地API；未安装其建议依赖或升级运行库。核心实现/验收未委派。聊天配置沿用已核实Sol/High，当前单次执行参数unknown。')
entry=dict(status='PASS_REQUIRED_NO_BOARD_RUNTIME_AND_DEPLOYMENT_VALIDATION',
    summary=str(summary_path.relative_to(ROOT)).replace('\\','/'),plan='docs/A12_REALTIME_MISS_OPTIMIZATION_4H_PLAN_20261027.md',
    entry='release/a12_realtime_model_draft_20261027_v1/START_HERE.md',evidence=str(EV.relative_to(ROOT)),
    real_browser_pairs=25,serial_browser_median_ms=879.0,realtime_browser_median_ms=618.3,
    realtime_browser_under_1s='23/25',answer_cache_hits_in_performance_test=0,
    actual_model_requests_per_group=25,final_native_cases=198,all_final_target_greedy_EOS_checker_pass=True,
    native_pc_sha256=pc['sha256'],native_arm_sha256=arm['sha256'],threads=3,prefix_tokens=34,continuous_output_limit=32,
    worst_question_admission_runs=22320,web_tests=43,browser_regressions=15,BOARD='NOT_TESTED',board_actions=0,
    board_visible_answer_s=None,board_real_PL_miss=None,board_owner_restore_release=None)
status_path=ROOT/'docs/PROJECT_STATUS.json';old=status_path.read_bytes();old_obj=json.loads(old)
key='a12_realtime_model_miss_no_board_20261027';assert key not in old_obj
nl=b'\r\n' if old.startswith(b'{\r\n') else b'\n'
block=json.dumps({key:entry},ensure_ascii=False,indent=2).splitlines()[1:-1]
new=b'{'+nl+nl.join(s.encode('utf-8') for s in block)+b','+nl+old[1+len(nl):]
assert {k:v for k,v in json.loads(new).items() if k!=key}==old_obj
status_path.write_bytes(new)
review=dict(status='PASS_PC_RUNTIME_PACKAGE_SOURCE_VERIFIED',requirements=dict(
    M0='ordered historical contracts/config exit0',M1='strict greedy target verification; math/ABI unchanged',
    M2='198 original and198 final actual pairs; explicit output32 EOS fix and bounded replay',
    M3='fresh real browser25, no answer cache, actual cache miss/scoring/lifecycle',
    M4='43+15 regressions, real packaged browser25 and normal close, A53 build; archive receipt separate'),
    commands=receipts,final_native=final,real_browser_ab=ab,packaged_browser_ms=package_ms,
    actual_miss=miss,source_and_package_match=True,current_198_input_and_result_verification=True,
    BOARD='NOT_TESTED',board_actions=0,board_latency_s=None,board_PL_miss=None,board_restore_release=None,
    required_no_board_runtime_items_remaining=[],archive_completion_receipt='ARCHIVES.json (generated next)')
save(EV/'FINAL_REVIEW.json',review)
print(json.dumps(dict(status=review['status'],browser_before_ms=879,browser_after_ms=618.3,
    under_1s='23/25',actual_model_requests=25,catalog_reads=0,final_cases=198,BOARD='NOT_TESTED'),indent=2))
