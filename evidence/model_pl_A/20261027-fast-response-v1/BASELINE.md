# A12 fast response baseline and timing contract

本轮只执行 2026-10-27 方案 N0～N6。原实板网页/NativePL、原 Owner、planner、checker、病例、评分和 EOS 门槛接续；未执行 B0～B4。

- 网关来源：frontend/web-gateway-20261026，commit `40498c2388b6293d68f38907c71ffd8933a5803e`；从 `release/frontend_chat_20261026/engineering-package.zip` 提取到独立 `platform/qwen35/web/vendor/`。提取前字节摘要见 SOURCE_PINS.json。
- 普通已验收包：`evidence/model_pl_A/20261026-pl-authfix-board-v2/bundle-fixed-v2.zip`，SHA256 `55cb8fd6892c71c4c2989bf375950ae971179195fbc0809f6207fdf0131980e2`。
- 复用 ARM native：SHA256 `115d167265667f026594836760be12470876e2b001b9dc8b61773459da35efab`，没有重编译。
- facts-only-02 来源：`evidence/model_pl_A/20261026-short-prompt-v1/facts-only-02/`。25 项消息/事实/模板等价，原 forms/check/planner/scoring 保持字节或 AST 等价。
- 最终可交付目录唯一为 `release/a12_fast_response_20261027_v2/`；较早 prepared、candidates 和无 v2 的 release 是实施中间版本，不作为启动入口。
- PC 单独复用现有 x86 native（SHA256 `e4836476012f64aa0164079b8c7529c5e587517c5914ca8a6886a7f1c29d38f3`）和 CPU 数学库，不能据此声称 PL、A53 或 BOARD 性能。

初始历史契约和新版配置检查按顺序通过，原工作区清单另存 WORKTREE_BEFORE.txt。仅修改本轮明确文件，没有全仓暂存、清理或推送。

| 字段 | 起止/含义 |
| --- | --- |
| 浏览器 submitted_ms | 提交 fetch 前 performance.now，绑定 session_id/request_id |
| answer_ready_ms | 同一请求的原 answer.ready SSE 到达浏览器 |
| painted_ms | 核验答案 DOM 更新后两次 requestAnimationFrame 的浏览器观测；记录 visibility_state |
| submit_to_paint_ms | 同一浏览器时钟内的相对耗时；只有实际模型、同一请求、有效会话和可见页面才可评价目标 |
| accepted_to_first_token_observed_ms | Python 接收并保留该问到收到第一个真实 native token 事件，同一 monotonic_ns 时钟 |
| native ttft_ms / prefill_ms / decode_ms | native 自身阶段计时；不等于界面显示，嵌套在外层模型耗时内 |
| accepted_to_validated_ms | Python 接收到原 checker/EOS 核验完成 |
| accepted_to_published_ms | Python 接收到原发布回执和 answer.ready 发布前 |
| route/prompt_builder/template/worker_wall | 各自阶段；health/Owner 原检查已包含在 worker_wall，不另叠加 |

前后端只用请求身份关联，不相减不同进程的单调时钟。浏览器测试使用 HTTP/SSE 协议替身，结果不能作为真实模型网页时延。真实 CPU 模型测试经过完整网页后端发布与评价，但没有真实浏览器与模型连跑的 BOARD 时延。

实际工程模型/推理强度工具不可读写，均记 unknown；所有阶段推荐 gpt-6.1-sol/High，未声称切换成功。DeepSeek 只把五条已给定字段说明机械转换为表格，原输出另存，主代理逐行检查；核心实现及验收由主代理完成。
