# 成员 B：Qwen3.5 计算后端工作规则

本文件是 B00 建立的本地规则，不声明已通过 agents-md-generator 的托管配置验收。

- 工作边界为本目录。原 b1_reference、b2_hls、b3_hls、handoff 和任务包只读；不改 A/C 工程。
- 先读 PROJECT_STATUS.json、docs/b00/B00_CHECKLIST.md、当前阶段计划及失败记录。
- 目标模型为 Qwen3.5-0.8B 文本主干。只负责 SP_LINEAR_V1 计算后端，模型图、病例、语音不在本模块范围。
- contracts/ 是原样复制的公共规范；内部 w4a8_linear_v1/KernelMeta 为私有兼容实现。更改公共数学、布局或冻结核 ABI 前须获得用户确认。
- 当前唯一开发分支为 b/qwen35-compute。保留 B3 的 32 路基础，优先验证新尺寸，再做 tile 复用和受控双缓冲。
- 独立 dense golden 不调用待测核生成期望值；测试失败保留输入，不删例、不放宽门槛。
- tests/ 为本模块新增测试入口，tb/ 为继承的历史 HLS testbench。docs/plan_qwen35/tests 是任务包参考载荷，不是本模块执行证据。
- PC、Csim、综合、Cosim、实现、ARM64、BOARD 分域记录；历史证据不得冒充新模型通过；未测值为 null/NOT_TESTED。
- 不安装工具、不改全局环境、不登录或上板。后续板测按对应阶段授权和已核实平台执行。
- 首次 meta 清零；失败不消费 y；超时不视为 DMA 已停止。完整生命周期在 B04 实现验收。
- 任务包要求开发助手 GPT-6.1 Sol / High / Standard；本地文件不能更改或证明客户端选项，未经核实不得宣称设置已锁定。
