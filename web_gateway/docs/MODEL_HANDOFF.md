# 给模型部署负责人的第四任务接入说明

2026-10-26 补充：单次演示优先看 `BOARD_DEMO_QUICKSTART.md`。现已提供既有A12 BOARD `NativePL` 的同进程托管接入口，结果/回执的 `actual_backend` 扩展支持 `FPGA_REAL`，相应Schema随包更新。默认生成预算180秒可配置。旧CPU入口继续保留；本轮未做真实模型或实板验收。

## 本包交付什么

- 完整 `web_gateway` 源码、依赖快照、纯文字发布规则及机器可读回执 Schema。
- A02 五份固定业务模块、三份合成病例及原始 SHA256；冻结参考原件不改。
- A09 NativeW4A8 接入口、实时事件、单轮结果查询、取消和重复请求处理。
- 自动化证据，以及 `patient_web.acceptance` 本机 HTTP 验收工具。

不包含模型权重、sidecar 资产、原生二进制、虚拟环境、录音、私人运行日志、界面美术或板卡系统。本包没有替接收方完成真实模型部署或实板签核。

## 职责边界

模型运行时负责持久加载、可信初始化、请求编号关联、输出和 EOS、实际执行状态、取消及清空/隔离。应用层负责 AnswerPlan、事实检查、正式发布、历史与评分；网页负责操作与展示。

模型输出是 candidate。模型运行时不调用 `publish_text()`，浏览器不提交“检查通过”“已播放”或病例事实。只有通过应用检查、仍属于当前有效任务的文字会生成交付回执。

## 当前真实入口

`TextEngine(backend='native', project_root=..., output=..., threads=3)` 固定接入：

- `system_qwen35.app.native_w4a8.NativeW4A8`
- `system_qwen35.app.default_e2e.prompts.prepare(messages, 'facts_v4')`
- `modules/linear_A/manifest.a09.json`

上游 NativeW4A8 继续校验模型、72 个 MLP 权重、原生二进制、物理微批和运行图身份。本包不绕过这些检查。

如果接收方已推进 A10/A11 或更新版本，先核对这些三个入口是否兼容；需要改动时仅调整本包适配层与接线测试，不能静默跳过清单/hash 或改写 A02 冻结参考。

## 适配调用与返回

调用接口是 Python `generate(messages, timeout_s=20)`，在单个活动线程内使用。messages 已由应用根据本轮允许事实构造，不能再拼入整份病例或未经确认的历史。

调用前，`trace_context` 包含 session_id、request_id 和网页 epoch。上游私有 IPC 的 id 应为 `session_id:request_id`；如果返回了 id，接口层会再次比对。结束后清除 trace_context。

归一化结果必须包含：

```json
{"text":"每次疼痛持续10分钟。","status":"OK","eos":true,"actual_backend":"CPU_REFERENCE"}
```

此处是格式示例，不是本包已经执行真实模型的证据。`eos` 必须是布尔值，不能是字符串。额外性能/状态字段可保留在原生日志中，不直接暴露给浏览器。

- OK + 完整 EOS：进入业务事实检查；失败可转显式 TEMPLATE。
- OK + eos=false：原候选不可发布，只能发布经过检查的保守回复。
- CANCELLED：结束本轮，不发布患者回答。
- ERROR 或 RuntimeError：本轮失败，不发布；native 上下文隔离。
- TIMEOUT 或 TimeoutError：按原 A02 超时保守回复执行最终检查，来源 TIMEOUT；native 标记 broken，后续拒绝推理，需明确重启。
- 畸形字段、错误 id 或声称不支持的 FPGA 后端：失败，不发布，native 隔离。

`healthy` 必须能真实反映可复用状态。取消请求只表示意图；适配器的活动调用返回并完成清理之前，接口仍为 BUSY。同步调用不能在接收 cancel 后立即放行另一个任务。

## 在接收方环境运行

先使用 **已有且匹配模型运行时的 Linux Python 3.12 环境**，核实上游资产。依赖锁为本机 Windows 开发快照，ARM64 wheel/系统库要在目标环境复核，不能复制 `.venv` 到板端。

解压后进入 `web_gateway` 目录，在上述环境安装本包：

```bash
python -m pip install -e .
```

该命令安装网页服务依赖，不会安装模型权重或替代原生运行时；目标机不能联网时，需由部署负责人预先准备匹配该架构的依赖 wheel。

启动示例（路径均替换为接收方实际值，output 必须是新目录）：

```bash
python -m patient_web --backend native \
  --project-root /actual/A-project \
  --output /actual/new-native-log-directory --port 8000
```

只启动一个服务进程，不增加 workers，不使用原 A08 `unshare -Urn` 包住网页入口。页面、HTTP 与 SSE 都在本机回环地址。真实模式缺资产会明确失败，不能切成 demo 后继续提交 native 验收结果。

在 **没有正在使用的问诊会话** 的服务上运行：

```bash
python -m patient_web.acceptance --base-url http://127.0.0.1:8000 \
  --expected-backend native --output /actual/new-delivery-result.json --timeout 180
```

该命令会创建一场合成问诊，验证回执内容与身份、重试、快照恢复、结束后稳定性；发现已有开放会话会拒绝，不会关闭他人的会话。output 文件不得预先存在。退出 0 才是 PASS；2 表示失败或仅模板回退的 PARTIAL。

## 请返回哪些联合验收结果

1. 上述原始 JSON 验收文件；保留 verdict、answer_source、model_called、actual_backend 和回执。
2. 实际工程版本、Python/架构、上游 manifest 与模型 revision；固定证据可从原生启动日志取得。
3. 真实一次取消：回合收尾前 BUSY、迟到结果不发布，下一轮状态干净；保留原生日志和接口事件。当前自动化已覆盖软件竞态，但不能替代原生静止验收。
4. 切病例/新会话没有带入上一会话患者事实；原生 R0 状态重置证据。
5. 缺模型或依赖时实际失败，没有 demo/CPU/FPGA 静默替换。

本包 `docs/VERIFICATION.json` 和 demo 验收文件只证明电脑接口范围。接收方真实模型回执通过也不等于 PL/BOARD、声学或医学质量通过。第四任务的本机工作完成后，联合验收状态继续如实为待运行。

