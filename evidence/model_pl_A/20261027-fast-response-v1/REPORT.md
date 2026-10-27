# A12 fast response：N0～N6 无板完成

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
| 接收到首 token 事件 | 598.810 | 697.020 | 1054.656 |
| 接收到核验发布 | 1068.485 | 1328.247 | 2365.361 |

完整时钟/嵌套定义见 BASELINE.md。每条原模型结果、检查、网页交付、评价和相对阶段耗时均在 release-model。3 线程只有离线准备通过，新的模型生成/Board 性能未测。

## 源码、环境、失败和下一步

SOURCE_PINS.json 固定原网关；IMPLEMENTED_SOURCE_PINS.json 固定本轮实现；每包 DERIVATION.json 列出派生改动，MANIFEST.json 列出文件与 SHA，ARCHIVES.json 列出包 SHA。公共数学/ABI、模型权重、B 核、xclbin 和已验收普通包没有改变；ARM native 精确复用原摘要。较早候选目录不是最终启动入口。

网页依赖只装在 `/home/member-a/kv260-build/a12-fast-response-20261027-venv`，没有全局升级；实际 Python/依赖版本见 PC_ENVIRONMENT.json。工程增量不含权重、sidecar、整机镜像、凭据或许可证，部署依赖原有 `/opt/patient-qwen` 资产、匹配 irq2 平台与已安装网页环境。

所有前件失败保留，具体原因和定向修复见 FAILURES.json；未删例、放宽 checker 或将模板当模型。此次只复用必要检查，没有重型 profile、全位置 logits、原始状态导出、Vivado/Vitis、全故障矩阵或压力运行。

下一阶段按 START_HERE 及冻结 BOARD_SEQUENCE 运行 B0～B4：先普通短配对，再独立连续网页窗口和真实可见时延，最后原 Owner 正常恢复并独立确认释放。现有 Board 状态/授权不由本文更新或续期。

全部工程阶段推荐 gpt-6.1-sol/High。工具不能读取或切换实际设置，记 unknown；没有声称自动切换。DeepSeek MCP 一次仅机械转换五条技术字段说明为表格，主代理逐行核对；未委派设计、核心逻辑或验收。未提交/推送。
