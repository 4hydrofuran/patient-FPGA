"""Collect the bounded N0-N6 receipts; never connect to devices or run new tests."""
import hashlib
import json
from pathlib import Path
import shutil
import statistics

ROOT=Path(__file__).resolve().parents[3]
EV=Path(__file__).resolve().parent
RELEASE=ROOT/'release/a12_fast_response_20261027_v2'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

commands=['release-web-tests','binding-tests','final-config','release-model-command',
          'release-t2-package','release-legacy-package','release-t3-package','help-prepare','help-verify','archive-command']
receipts={name:read(EV/name/'COMMAND.json') for name in commands}
assert all(r['exit_code']==0 for r in receipts.values())
baseline=read(EV/'attempt01/BASE_CHECKS.json');assert [r['exit_code'] for r in baseline]==[0,0]
model=read(EV/'release-model/RESULT.json');browser=read(EV/'attempt06-browser/RESULT.json')
assert model['status']=='PASS_ACTUAL_CPU_WEB_MODEL' and model['model_items']==25 and model['policy_items']==7
assert model['model_calls']==33 and model['same_session_model_questions']==2 and model['same_session_frozen_score']==20
assert model['worker_exit_codes']==[0,0] and len(model['representative_pairs'])==3
assert all(r['equal'] for r in model['representative_pairs'])
assert browser['status']=='PASS_BROWSER_FIXTURES' and len(browser['checks'])==15 and not browser['model_executed']
archives=read(RELEASE/'ARCHIVES.json');assert len(archives)==3 and all(r['CRC_and_SHA_readback']=='PASS' for r in archives)
stats={k:dict(min=min(a),median=statistics.median(a),max=max(a),samples=len(a))
       for k in ('accepted_to_first_token_observed_ms','accepted_to_published_ms')
       if (a:=[r['timing'][k] for r in model['model_results']])}

pins=[]
files=[ROOT/'system_qwen35/app/native_pl.py',ROOT/'system_qwen35/app/web_managed.py',ROOT/'config/qwen35/web.fast-response.json']
web=ROOT/'platform/qwen35/web'
files += list(web.glob('fast_response*.py'))+[web/'short_prompt_adapter.py',web/'interactive_case.py']
files += [p for p in (web/'vendor/web_gateway').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
files += [p for p in (ROOT/'bench/qwen35/web').glob('*.py')]
for p in sorted(set(files)):
    pins.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
save(EV/'IMPLEMENTED_SOURCE_PINS.json',pins)
# Confirm the actual shipped consumer files equal the final source used by the targeted tests.
for package in ('short34-threads2','legacy70-threads2','short34-threads3'):
    for kind in ('ordinary','continuous'):
        window=RELEASE/package/kind
        for name in ('native_pl.py','web_managed.py'):
            assert sha(window/name)==sha(ROOT/'system_qwen35/app'/name)
        for p in (web/'vendor/web_gateway/src').rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                assert sha(window/'web_gateway/src'/p.relative_to(web/'vendor/web_gateway/src'))==sha(p)

failures=[
 dict(attempt='initial shell receipts',issue='PowerShell expanded shell variables; per-component exit values absent',
      resolution='baseline checks rerun sequentially and recorded as exit0; ambiguous first output not used for PASS'),
 dict(attempt='dependency install first shell call',issue='WSL shell interpreted an unpreserved < version constraint as redirection',
      resolution='explicit pinned arguments installed only in the task venv; PC_ENVIRONMENT.json records actual versions'),
 dict(attempt='attempt02-web-tests',issue='test read raw_text instead of the existing transcript field',
      resolution='correct existing schema; final 34 tests pass'),
 dict(attempt='attempt02-model',issue='verifier expected HTTP 200 for the original correct create-session 201 response',
      resolution='verifier fixed; model quality gate unchanged'),
 dict(attempt='attempt03-model',issue='verifier compared a dataclass tuple directly to a frozen JSON array',
      resolution='compare equivalent lists; original plans/required facts unchanged'),
 dict(attempt='attempt03-browser and attempt04-browser',issue='virtual-time timers did not establish real compositor-frame observations',
      resolution='run the existing headless Edge on real time via local CDP; no browser sandbox changes'),
 dict(attempt='attempt05-browser',issue='cursor/epoch comparison needed the same-session condition on refresh',
      resolution='session-scoped comparison and realistic global cursor fixture; all 15 final browser checks pass')]
save(EV/'FAILURES.json',dict(previous_attempts_preserved=True,rows=failures,unresolved_no_board_failures=[]))
review=dict(status='PASS_N0_N6_NO_BOARD_WORK_COMPLETE',release='release/a12_fast_response_20261027_v2',
    model_items=25,policy_items_zero_model=7,actual_CPU_model_generations=33,representative_pairs=3,
    same_session_questions=2,same_session_frozen_score=20,web_tests=34,binding_tests=6,browser_fixture_checks=15,
    commands=receipts,baseline_checks=baseline,archives=archives,PC_timing_ms=stats,
    BOARD='NOT_TESTED',board_actions=0,board_TTFT_s=None,board_visible_checked_answer_s=None,
    board_memory=None,hardware_global_count=None,within_10s_BOARD=None,
    threads3_new_model_validation='NOT_TESTED',actual_model='unknown',actual_reasoning_effort='unknown',
    recommended_model='gpt-6.1-sol',recommended_reasoning_effort='high',
    DeepSeek='ONE_MECHANICAL_TABLE_ONLY_NOT_EVIDENCE_ACCEPTANCE',pushed=False,
    remaining=['B0-B4 fresh Board identity/window, real PL pair, visible browser timings, original Owner restore/independent release'])
save(EV/'FINAL_REVIEW.json',review)
shutil.copyfile(EV/'PC_ENVIRONMENT.json',RELEASE/'PC_ENVIRONMENT.json')

report='''# A12 fast response：N0～N6 无板完成

唯一最终入口为 `release/a12_fast_response_20261027_v2/START_HERE.md`。本轮没有连接板卡或执行 Owner/PL 操作；新 BOARD 为 NOT_TESTED，板端首 token/可见核验回答/内存/硬件计数与 10 秒达标均为 null。历史实板 PASS 与失败不改写。

## 已实现

- 冻结网关只添加宿主内部 prompt_builder 注入点；默认保留旧 prompt。facts-only-02 的 25 项完整事实句、消息和模板逐项等价，原 checker/forms/planner/scoring 保持。
- 实例 profile 同时用于准备器、prefix 配置、transport、warm/ready 与预算。短候选使用 34-token 独立 cache ID；真实命中、复用数与实际 binding 必须一致，miss 不转 R0。正常生成的实际 token 前缀边界已通过 CPU 检查。
- 1024/34/24 完整上下文逐问预留 10584；本次选中的持续时间代表请求普通 R0/warm/hit 最坏 4320/5000。固定语料最长 55 时的示例 4392 只用于公式回归，不冒充本次选中请求的预算。连续窗口为独立 60000/14400 秒，所有工作量 authorization_included=false。
- 复用原 SSE 与 session/epoch，合并刷新、保留旧 DOM 和断线轮询；中文选字 Enter 不提交，明确提交只发一次。浏览器记录核验答案的绘制观测，后端记录同钟首 token 与最终发布；不混减时钟或重复累加 health 耗时。
- NativePL 在全局函数设置后只编译一次 Jinja；正常结束场次只冻结评分，worker/cache 继续复用。原动态健康、锁、Owner、完成和正常关闭逻辑保留。未实现 P2 状态机制重写。

## 实际结果

| 检查 | 结果/证据 |
| --- | --- |
| 历史契约 → 新版配置 | 按顺序 exit0，attempt01/BASE_CHECKS.json；最终配置检查另 exit0 |
| 原/新网页接线与定向回归 | 34 项 exit0，release-web-tests |
| 原授权绑定回归 | 6 项 exit0，binding-tests |
| 真实 CPU 网页后端固定输入 | 25/25 MODEL、原 checker/EOS、原文未替换，release-model/RESULT.json |
| 策略输入 | 7 项零模型；保持原 route |
| 代表配对 | DEV-012（最长/双事实）、DEV-011（未知）、V08（双事实）三组 R0/hit 输出及最后 prefill logits 摘要相等 |
| 连续会话 | 同一真实 CPU worker/cache，两问后冻结 20 分；新病例/场次复用；见 CONTINUOUS.json |
| 旧身份拒绝与关闭 | 旧 70-token prefix 和旧 binding 真实拒绝；tokenizer/model 两个 PC worker 均 exit0 |
| 本地浏览器 | 真实 headless Edge 上 15 项 HTTP/SSE 协议替身检查通过，attempt06-browser；没有真实模型/PL，不计模型时延 |
| 独立 profile/窗口 | 短 2、旧 70、短 3 三份 profile 的 ordinary/continuous 均通过离线真实导入与预算检查；无 Owner/worker/设备启动 |
| CLI/封包 | prepare/verify --help exit0；三个 ZIP 逐文件 CRC/SHA 回读通过，ARCHIVES.json |

最终套件 33 次实际 CPU 生成 = 25 固定输入 + 3×2 配对 + 2 同场问答。较早成功 31 次套件是计时补齐前的中间版本，另存 final-model，不混入最终样本计数。PC 使用现有 x86 binary，不把 CPU 数学库视为 PL。

## 计时与边界

以下只是最终 PC 的 25 个不同固定输入描述值；没有真实模型与浏览器连跑的 BOARD 测量，没有 p95/SLA，也不据此预测 A53/PL。浏览器替身约毫秒级数据不纳入下表。

| Python 同钟相对耗时（ms） | min | median | max |
| --- | ---: | ---: | ---: |
'''
for key,label in [('accepted_to_first_token_observed_ms','接收到首 token 事件'),('accepted_to_published_ms','接收到核验发布')]:
    v=stats[key];report+=f"| {label} | {v['min']:.3f} | {v['median']:.3f} | {v['max']:.3f} |\n"
report+='''
完整时钟/嵌套定义见 BASELINE.md。每条原模型结果、检查、网页交付、评价和相对阶段耗时均在 release-model。3 线程只有离线准备通过，新的模型生成/Board 性能未测。

## 源码、环境、失败和下一步

SOURCE_PINS.json 固定原网关；IMPLEMENTED_SOURCE_PINS.json 固定本轮实现；每包 DERIVATION.json 列出派生改动，MANIFEST.json 列出文件与 SHA，ARCHIVES.json 列出包 SHA。公共数学/ABI、模型权重、B 核、xclbin 和已验收普通包没有改变；ARM native 精确复用原摘要。较早候选目录不是最终启动入口。

网页依赖只装在 `/home/member-a/kv260-build/a12-fast-response-20261027-venv`，没有全局升级；实际 Python/依赖版本见 PC_ENVIRONMENT.json。工程增量不含权重、sidecar、整机镜像、凭据或许可证，部署依赖原有 `/opt/patient-qwen` 资产、匹配 irq2 平台与已安装网页环境。

所有前件失败保留，具体原因和定向修复见 FAILURES.json；未删例、放宽 checker 或将模板当模型。此次只复用必要检查，没有重型 profile、全位置 logits、原始状态导出、Vivado/Vitis、全故障矩阵或压力运行。

下一阶段按 START_HERE 及冻结 BOARD_SEQUENCE 运行 B0～B4：先普通短配对，再独立连续网页窗口和真实可见时延，最后原 Owner 正常恢复并独立确认释放。现有 Board 状态/授权不由本文更新或续期。

全部工程阶段推荐 gpt-6.1-sol/High。工具不能读取或切换实际设置，记 unknown；没有声称自动切换。DeepSeek MCP 一次仅机械转换五条技术字段说明为表格，主代理逐行核对；未委派设计、核心逻辑或验收。未提交/推送。
'''
(EV/'REPORT.md').write_text(report,encoding='utf-8')
print(json.dumps(dict(status=review['status'],model_calls=33,archives=3,remaining='BOARD B0-B4'),indent=2))
