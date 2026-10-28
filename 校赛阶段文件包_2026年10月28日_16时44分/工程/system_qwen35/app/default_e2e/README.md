# A08 默认电脑整机服务

这是教师审核前的软件演示，不是临床系统。默认计算与语音均为 A，未安装 B/C 不影响启动。保留 A05 旧入口、模型、原始测试和公共协议。

## 一个启动命令

在项目 WSL 内执行（输出目录必须尚不存在）：

```bash
bash platform/qwen35/a08/run.sh -m system_qwen35.app.default_e2e --output eval/qwen35/a08/manual-001
```

`run.sh` 创建无外网网络命名空间，不改宿主联网状态。终端是主应用界面：直接输入问题，或 `/wav /absolute/question.wav`；`/case SYN_CP_02`、`/status`、`/cancel`、`/restart`、`/quit`。不启动麦克风。播放使用 WSLg Pulse Unix socket；所有临时音频只在该实例独占 spool 内处理。

单轮参数：`--text '疼痛在什么位置？'` 或 `--wav ...`。`--mode no_hardware` 明确以同数学 CPU 运行。`--mode fpga_required` 在创建服务/模型/设备前报 `HARDWARE_UNAVAILABLE`，退出 2，不回退。

## 调度和证据

- 一轮在途，待办轮队列容量 0（忙时拒绝），worker 队列 4，IPC 等待项 8。
- LISTEN/ASR → GENERATE → VALIDATE → SYNTHESIZE → PLAY 串行。不同时启动三方模型计算。
- 显式比较 LLM 2/3（包括优化 W4A8 算子）、ASR 1、TTS 1/2；环境限制 OMP/BLAS 隐式池，但算子使用显式 `num_threads`。线程对象数量不等于同时活跃计算线程数。
- 使用原 SP_VOICE_V1；200ms 顺序块收到 ack 才清理。未声明流式能力时必须显式使用完整 WAV，不偷偷切协议。
- 语音请求 `session_id` 和 spool 首层是真实业务 UUID；模型私有 IPC `id` 为 `session_id:request_id`，请求另带 session/epoch。不同进程通过同一会话/请求关联，不把固定音频槽位当会话。语音登记达到 7 个会话时只重启语音 worker，保持模型驻留。
- R0 清空并重算，前缀缓存禁用。gate/up 图内激活复用不等于应用答案缓存。每次请求都真的计算；无预录回答。
- 模型输出与模板/超时来源分列。模板不伪称 CPU 模型回答；是否真正调用模型另看 `actual_backend` 和 IPC。
- 完整回答通过事实检查后才进入 TTS。默认一份完整 WAV，未启用句间重叠或推测播放。
- 主应用、语音和播放器使用同一 Linux `CLOCK_MONOTONIC`；首 token 是真实原生 token 事件的 IPC 接收边界，原生 prefill/TTFT 单独保留。
- 文件提交不是现场说话结束，Pulse drain 不是声学起点；相关未测字段为 null。日志保留所有失败、取消、超时及其未完成时间。
- 取消增加 epoch，迟到结果不消费，未完成播放不进历史；模型每轮 R0 清空。播放在拥有的独立进程内，有实际时长+10s 墙钟期限；取消最多等待 1s 后只终止自己启动的播放器。物理出声/停止仍需回采。
- 每轮 reset 确认 worker 无在途工作，再只清理本实例创建的文件。达到语音请求/会话预算时在维护窗口只重启语音 worker，不重载语言模型；语言模型超时隔离后才做明确的整组恢复。不删除用户输入 WAV，不清理其他目录。
- `config/qwen35/resources.a08.json` 是有效默认值快照，不是任意值配置加载器；执行参数由 CLI `--llm-threads`、`--tts-threads` 覆盖，并在 `startup.json` 记录实际配置。未证明收益的短提示 v1/v2/v3 不成为默认值。

`rounds.jsonl` 保存完整逐轮记录，`resources.jsonl` 每 500ms 采样主应用/模型/语音/播放器的 RSS/PSS、文件页和线程数，`maintenance.jsonl` 保存启动/取消/切病例/恢复。S1 的 sidecar、保护后的原 GGUF 目标页和 workspace 由原生报告解释，不把磁盘字节重复加到进程 RSS。

## 回归

```bash
bash platform/qwen35/a08/run.sh platform/qwen35/a08/regression.py eval/qwen35/a08/regression-NEW
```

先固化 200 个合成 WAV 用例；另记必要故障注入和无硬件模式。2026-10-03 用户要求停止过量重复，默认不再追加按时长循环；仅再次明确要求长测时才使用 `--minimum-seconds 7200`。不会用空等补足时长。相同 TTS 生成的重复合成问句仅用于工程可靠性，不是自然人群 ASR 准确率、独立 300 条终测或医学有效性。现有200轮已完成，不因修改默认参数重跑。

交互式 `/wav` 已在 A09 接入人工转录确认：出现 `transcript_review` 后，输入 `/confirm <ticket> yes` 或 `no`；超时、拒绝及取消均保守处理。单次 `--wav` 不提供交互确认，因此没有可信置信度时仍会澄清。控制测试不等于真人使用验收，合成测试原句核对不等于真人确认。可直接输入文本使用真实模型。

每轮记录配置哈希、模型 revision、运行时 commit、模型/sidecar/语音锁文件哈希和病例版本/哈希；不会每 token 重哈希或重载权重。资源采样缺失的总量为 null，保留可观测小计、缺失项与错误计数，不能把读不到的进程当作0。500ms采样峰值不是连续真实峰值。

所有 BOARD、A53 内存、CMA、BO 预算和功耗仍为 NOT_TESTED/null。Matcha/Baker 资源非商业限制保留，不发布权重。
