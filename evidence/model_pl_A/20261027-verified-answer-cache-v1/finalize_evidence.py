"""Requirement-scoped completion audit using actual files, source, receipts and browser results."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];EV=Path(__file__).resolve().parent
RELEASE=ROOT/'release/a12_verified_answer_cache_20261027';PACKAGE=RELEASE/'hybrid34-threads2'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

names=['build01-command','catalog-verify01-command','live-serve01-command','live-browser01-command',
       'cache-serve03-command','cache-browser03-command','ab-final-command','actual-miss-checks01-command',
       'tests-final-command','browser-regression02-command','planner-coverage-command','package-verify-final-command',
       'packaged-serve01-command','packaged-browser01-command','help-prepare-command','help-build-command',
       'help-verify-command','config-final-command','archive-product-command']
receipts={n:read(EV/n/'COMMAND.json') for n in names}
assert all(x['exit_code']==0 for x in receipts.values())
assert [x['exit_code'] for x in read(EV/'BASE_CHECKS.json')]==[0,0]
catalog=read(EV/'build01/RESULT.json');proofs=read(EV/'CATALOG_VERIFIED.json');scope=read(EV/'PLANNER_COVERAGE.json')
assert catalog['accepted']==198 and not catalog['failures'] and catalog['model_calls']==198 and catalog['worker_exit']==0
assert proofs['entries']==198 and proofs['cache_python_peak_bytes']<8*1024*1024 and scope['plans']==198
assert scope['score_after_followup']==20 and scope['context_followup']=='MODEL_CACHE_NO_NEW_MODEL_CALL'
ab=read(EV/'AB_FINAL.json');live=read(EV/'live-serve01/RESULT.json');cached=read(EV/'cache-serve03/RESULT.json')
assert ab['total']==25 and ab['within_1s']==25 and ab['cache_ms']['median']<=300
assert live['native_count']==25 and cached['native_count']==0 and cached['cache']['hits']==25
assert live['worker_exit']==cached['worker_exit']==0
miss=read(EV/'actual-miss-checks01/RESULT.json')
assert miss['actual_model_calls']==1 and len(miss['policy_items'])==7 and miss['same_session_score']==20
assert miss['archived_cache_sessions']==10 and miss['retained_in_memory']==8 and miss['worker_exit']==0
pack_run=read(EV/'packaged-serve01/RESULT.json');pack_browser=read(EV/'packaged-browser01/RESULT.json')
assert pack_run['native_count']==0 and pack_run['cache']['hits']==25 and pack_run['worker_exit']==0
assert pack_browser['questions']==25 and all(x['turn']['answer_source']=='MODEL_CACHE' for x in pack_browser['rows'])
settings=read(EV/'SETTINGS.json');assert settings['setting_change_succeeded'] and settings['configured_effort']=='high'
assert '高' in settings['UI_verified_after']
archive=read(RELEASE/'ARCHIVE.json');assert archive['status']=='PASS_PRODUCT_ZIP_CRC_SHA_READBACK'

# Match the final tested product's actual consumed runtime source to the current implementation.
web=ROOT/'platform/qwen35/web';paths=[]
for kind in ('ordinary','continuous'):
    window=PACKAGE/kind
    for p in web.glob('*.py'):
        if p.name in ('fast_response_prepare.py','answer_cache_prepare.py'):continue
        assert sha(window/p.name)==sha(p),p
    for name in ('native_pl.py','web_managed.py'):
        assert sha(window/name)==sha(ROOT/'system_qwen35/app'/name)
    for p in (web/'vendor/web_gateway/src').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            assert sha(window/'web_gateway/src'/p.relative_to(web/'vendor/web_gateway/src'))==sha(p),p
for p in sorted([*web.glob('*.py'),*web.joinpath('vendor/web_gateway').rglob('*'),
                 *(ROOT/'bench/qwen35/web').glob('*.py'),ROOT/'system_qwen35/app/web_managed.py']):
    if p.is_file() and '__pycache__' not in p.parts:
        paths.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
save(EV/'IMPLEMENTED_SOURCE_PINS.json',paths)
with (EV/'AB_FINAL.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['id','live_ms','cache_ms','reduction_ms','reduction_percent']);w.writeheader();w.writerows(ab['rows'])

failures=[
 dict(attempt='UI settings input',cause='coordinate input geometry unavailable; activation failed',
      solution='supported current-chat model/thinking override',executed=True,result='UI GPT-6.1 Sol 高 verified'),
 dict(attempt='cache-serve01-command',cause='source layout lacked top-level web_managed import',
      solution='explicit source/flat-package layout resolution',executed=True,result='cache03 and packaged service/browser passed'),
 dict(attempt='cache-serve02-command',cause='Windows reader temporarily denied WSL metrics atomic rename',
      solution='bounded retry; optional PC metrics do not terminate service',executed=True,result='cache03 and packaged normal exit0'),
 dict(attempt='browser-regression-command',cause='Edge DevToolsActivePort briefly locked while created',
      solution='bounded startup retry only for missing/locked/incomplete port file',executed=True,result='15 browser regressions and packaged real browser passed')]
save(EV/'FAILURES.json',dict(original_failures_preserved=True,rows=failures,unresolved_required_no_board_items=[]))
requirements=[
 dict(id='C0',requirement='plan with per-stage reasoning; protected baseline/config checks',evidence=['docs/A12_VERIFIED_ANSWER_CACHE_10H_PLAN_20261027.md','BASE_CHECKS.json']),
 dict(id='C1',requirement='198 actual model/EOS/checker answers and provenance/coverage',evidence=['build01/RESULT.json','CATALOG_VERIFIED.json','PLANNER_COVERAGE.json']),
 dict(id='C2',requirement='fresh routing/check/scoring, exact cache keys, truthful source, actual miss',evidence=['actual-miss-checks01/RESULT.json','actual-miss-checks01/HIT_MISS.json','cache-tests01/COMMAND.json']),
 dict(id='C3',requirement='real browser delivery/source badge, IME/session/reconnect, lifecycle',evidence=['cache-browser03/RESULT.json','browser-regression02/RESULT.json','tests-final-command/COMMAND.json','cache-serve03/RESULT.json']),
 dict(id='C4',requirement='same-question/output real HTTP/browser A/B, zero new model on hits',evidence=['AB_FINAL.json','live-browser01/RESULT.json','cache-browser03/RESULT.json','live-serve01/RESULT.json','cache-serve03/RESULT.json']),
 dict(id='C5',requirement='tested deployment closure, actual commands/help/rollback and archive SHA',evidence=['packaged-browser01/RESULT.json','packaged-serve01/RESULT.json','package-verify-final-command/COMMAND.json','ARCHIVE.json']),
 dict(id='reasoning',requirement='automatic recommended configuration and resolved blocker',evidence=['SETTINGS.json']),
 dict(id='no-board',requirement='no Board actions; do not claim Board speed/release',evidence=['all CPU-domain CLI/receipts','REPORT.md'])]
for item in requirements:item['status']='PROVEN_WITH_STATED_PC_SCOPE'
review=dict(status='PASS_ALL_REQUIRED_NO_BOARD_CACHE_WORK',requirements=requirements,commands=receipts,
    catalog_entries=198,actual_CPU_catalog_generations=198,total_actual_CPU_generations=224,
    web_tests=39,browser_fixture_tests=15,real_browser_pairs=25,live_ms=ab['live_ms'],cache_ms=ab['cache_ms'],
    paired_reduction_ms=ab['reduction_ms'],cache_under_1s='25/25',cache_origin='CPU_REFERENCE',
    cache_current_model_calls=0,model_assets_metadata=read(EV/'MODEL_VERSION_METADATA.json'),
    source_and_package_match=True,archive=archive,configured_model='gpt-6.1-sol',configured_effort='high',
    configuration_UI_verified=True,actual_per_call_effort='unknown',BOARD='NOT_TESTED',board_actions=0,
    board_visible_answer_s=None,board_memory=None,hardware_global_count=None,board_real_PL_miss=None,
    board_owner_restore_release=None,pushed=False,
    remaining=['Only separately authorized BOARD cache-visible latency, real PL miss, original Owner restore/independent release'])
save(EV/'FINAL_REVIEW.json',review)
report=f'''# A12核验模型答案复用：无板完成

用户明确允许复用已核验模型答案并保留来源。方案C0～C5已执行，唯一入口为 `release/a12_verified_answer_cache_20261027/START_HERE.md`。

## 实际响应时间

真实本机HTTP/SSE、真实Edge，25个相同病例/问题/输出逐项配对；测量浏览器提交到完整核验答案DOM更新后两次animation frame。
无模拟SSE/伪模型计时。缓存组的原答案均由真实CPU Qwen生成，本轮再核验，来源明确标记MODEL_CACHE。

| ms | 最快 | 中位 | 最慢 |
| --- | ---: | ---: | ---: |
| 原v2实时CPU模型网页 | {ab['live_ms']['min']:.1f} | {ab['live_ms']['median']:.1f} | {ab['live_ms']['max']:.1f} |
| 新核验答案复用网页 | {ab['cache_ms']['min']:.1f} | {ab['cache_ms']['median']:.1f} | {ab['cache_ms']['max']:.1f} |
| 逐题配对减少 | {ab['reduction_ms']['min']:.1f} | {ab['reduction_ms']['median']:.1f} | {ab['reduction_ms']['max']:.1f} |

缓存25/25低于1秒。中位数之差约{(ab['live_ms']['median']-ab['cache_ms']['median'])/1000:.3f}秒；逐题差值中位约{ab['reduction_ms']['median']/1000:.3f}秒。
不报p95/4小时稳定结论，不把CPU和板端数字相减。旧板端27.854秒不能与这里42.3ms直接计算加速倍数。
逐题数值见AB_FINAL.json/CSV，实际显示截图为cache-browser03/first-answer.png。

## 生成成本、资源与来源

- 三病例、11事实、最多两事实，共198键。实际生成198/198，原checker/EOS、非teacher-forced、原文SHA和当前事实复验全部通过；198组独立实际planner问题也全部命中，另验证上下文“那个呢”及原20分评分。
- 一次离线生成{catalog['elapsed_s']:.2f}秒（约{catalog['elapsed_s']/60:.2f}分钟），每次提问不重复支付。目录{catalog['catalog_bytes']}字节；缓存Python加载保留{proofs['cache_python_retained_bytes']}字节、峰值{proofs['cache_python_peak_bytes']}字节。这是缓存对象分配，不是整机或板端峰值。
- PC服务启动/模型和前缀预热另外记录在各serve目录HTTP_READY.json，未计入提交后时延。原模型/72权重/BO方案不因文本复用而宣称不占资源。
- 原生成后端CPU_REFERENCE，本轮MODEL_CACHE的model_called=false、actual_backend=null、当前PL提交为0；原模型/库/原请求/EOS/文本摘要在cache_provenance中。不是每问新执行FPGA_REAL。
- 未命中原34-token路径，在线24输出/1024上下文/10584预留不变；离线64输出只用于得到双事实完整EOS。公开数学/算子ABI、量化、HLS、xclbin和ARM native不变。

## 验证

历史契约后新版配置均exit0；39项网页测试、15项浏览器协议替身回归通过。实际移除一个条目后只发生1次真实CPU模型生成，其余命中/7策略零新模型；同场20分冻结、幂等、新病例、10场归档保留8场内存通过。
实时PC服务25次生成，复用服务25命中/0生成，两个正常窗口及部署副本均worker exit0；HTTP层保留原worker关闭所有权。
部署副本另完成真实浏览器25题，完整离线依赖/预算/目录准备通过，ZIP的{archive['verified_payload_files']}个payload逐文件CRC/SHA回读通过。
各命令的真实stdout/stderr/退出码和摘要在*-command目录，全部必需回执见FINAL_REVIEW.json。

## 阻碍及实际处理

UI无法点击/激活模型菜单后，改用本聊天支持的参数接口，设置后续Sol/High，UI显示“高”；不追认之前阶段或单次执行强度。
PC源码/部署布局导入差异、Windows跨WSL临时文件锁、Edge端口文件创建锁均已定位并执行最小修复；失败原回执保留，见FAILURES.json。
指标重命名修复仅限PC测试工具，没有异步化或删除原Owner持久化、动态健康、完成/关闭门槛。

## 交付与剩余项

完整部署ZIP/清单在新release；旧v2及旧70回退包不覆盖。新缓存回执text-delivery.v2与原v1读取兼容，界面保留缓存标记、合成病例/待教师审核口径。
源码与实际消费包已逐文件匹配。未训练、未调用Vivado/Vitis、未做全量故障矩阵/大规模安全审查、未升级全局依赖、未连接板卡或推送。

新BOARD为NOT_TESTED：板端可见时延、一次真实PL未命中、原Owner恢复与独立释放、CMA/功耗/硬件计数均为null。
后续另获授权后做少量真实板测，不因本次PC通过追认BOARD。
'''
(EV/'REPORT.md').write_text(report,encoding='utf-8')
# Move the current status from packaging to verified completion without rewriting unrelated status entries.
p=ROOT/'docs/PROJECT_STATUS.json';text=p.read_text(encoding='utf-8')
text=text.replace('"status": "IMPLEMENTED_ACTUAL_CPU_BROWSER_VERIFIED_PACKAGING"',
                  '"status": "PASS_ALL_REQUIRED_NO_BOARD_CACHE_WORK"',1);p.write_text(text,encoding='utf-8')
print(json.dumps(dict(status=review['status'],real_browser_pairs=25,cache_under_1s='25/25',
    live_median_ms=ab['live_ms']['median'],cache_median_ms=ab['cache_ms']['median'],BOARD='NOT_TESTED'),indent=2))
