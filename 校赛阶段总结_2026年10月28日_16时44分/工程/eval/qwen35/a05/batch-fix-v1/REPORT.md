# A05续作收口报告

2026-10-02 · A-DESIGN-1.0 · 无板 · `PASS_PC_A05_FULL_MODEL_PHYSICAL_T8`

## 结论及范围

72个Qwen3.5-0.8B MLP已真实走原SP_LINEAR_V1同数学CPU后端，默认物理微批T=8，支持T1/2/4/8及尾块。原先物理分块数值失败已修复，完整文本与离线合成语音问诊复测通过。本结论只通过A05电脑工程门禁，不是临床质量、KV260性能或G1通过。

不换模型、不改公共数学/容差、不重新导出权重、不以内部整图T1冒充物理T8。R1/R2可选而未启用；R0清空全部混合状态重算。未自动进入A06。

## 实际改动与原因

1. `runtime/qwen35_w4a8/sp-hook.*`：非MLP权重投影拆为原生SIMD GEMV后拼回批量输出。原库按批量选择tiled/repack GEMM/GEMV，舍入微差会改变A8码。原失败样本首层gate/up有11个A8码差异，down有128个。仅关闭其中一条tiled路径不能解决全部T4/T8问题。MLP自定义节点仍真正处理多token，不逐层跨Python进程。
2. 固定源码隔离副本的`ggml-cpu/ops.cpp`：原FlashAttention在单查询、KV长度>=512时启用split-KV并改变归约顺序，较大查询还可走tiling。S1明确使用原逐查询SIMD核及线程分工，固定这两处选择；不重写注意力公式，不关闭整个运行库的优化。原S0运行库未动，S1非MLP权重/精度不变，但浮点调度变化明确列入S0→S1的图改动。
3. `main.cpp`：物理T8默认/合法范围、实际调度身份、受限节点诊断；合法零输出位置走上游空张量语义。v6在final-logits中间块将空concat返回null、退出-11，最小复现保存，修复后正常模式通过。没有强制all-logits掩盖错误。
4. `bridge.*`：记录真实成功CPU调用的T直方图。保留原缓存epoch/层/执行号/shape/一次消费有效期、down重新量化、响应前状态清理、权重一次加载及GGUF目标页保护。
5. `system_qwen35/app/native_w4a8.py`：读取已核验manifest的入口，核对物理T8与注意力/投影调度身份；缺失或错配硬失败，不静默切S0。`modules/linear_A/manifest.json`指向最终v8。
6. `platform/qwen35/a05/`新增隔离构建、节点定位、崩溃复现、多提示/长输入回归、收口审计；测试客户端在native崩溃后保留退出码，避免BrokenPipe清理异常遮盖记录。治理状态/差距/交接已更新。

量化计算、CPU算子实现、原始权重及72份sidecar完全未改。公开契约仍为原SHA256，未创建并行公共协议。

## 最终构建的真实验证

| 验证域/内容 | 结果与证据 |
|---|---|
| PC物理T1/2/4/8及尾块 | `state-v8/numerics.json`：23位置完整248320维logits、48组KV/递归/卷积状态数组逐位相同；所捕获投影输入/输出逐位相同 |
| PC scalar/optimized | 同一输入的24层72个投影、logits、混合状态逐位相同；不是相对原浮点模型零误差 |
| PC旧安全路径保护 | `canonical-history-comparison.json`：固定短样例的最终T8与旧canonical T1，72投影/23位置/48状态数组逐位相同 |
| PC状态功能 | `state-v8/checks.json`：17项通过，含实际SIGUSR1取消、reset、拒绝R1、未播重算、病例切换、256/1024token、权重只加载72次 |
| PC补充 | `extra-batch-v8/report.json`：74断言通过；3种多轮/否定/拒绝提示以及257/1025token尾块，比较全词表与增量decode。1025token原失败在T1/T8/整段间最大logits差由1.715724945降至0 |
| PC真实T证据 | 22token+1次teacher decode：T2=792次、T4=360次、T8=144次对应的CPU调用；尾块T6=72次。每次执行真实数值，不是硬件计数 |
| PC应用 | `app-dev-v8/S1-summary.json`：24条开发题、80断言；17 MODEL/7预期策略TEMPLATE，0非预期回退，真实超时/错误隔离独立标记 |
| PC离线语音 | `voice-s1-v8/summary.json`：两条已有合成WAV，断网进程树中真实ASR→病例/S1→检查→TTS→WSLg播放API完成；未新录音、声学起点null |
| 既有PC算子证据 | 最终SP CPU库与v3的SHA256相同；保留103 ABI检查和48真实SIMD整数/FP32独立参考，不把重复跑计为新样本 |
| 保护检查 | 开始/结束旧契约及新配置均退出0；开工原seal12523项全部匹配 |
| Csim/Cosim/综合/实现/ARM64/BOARD | 全部NOT_TESTED；本次未调用，硬件误差/功耗/Linux板内存/BO预算null |

诊断整图容差仍为atol=0.002、rtol=0.0002；算子为1e-4/1e-5。本次实际相同比较为逐位一致，未调整容差。teacher token是固定诊断输入，不冒充自然生成答案。全72投影捕获主要用于整段/scalar；其余分块同时核对0/3/4/23层边界；较早stable-probe-v1另有所有分块的72投影数据。应用和长输入使用final-logits正常模式。

## 性能、质量与内存分账

开发集17次模型调用，平均提示107.76token、PC TTFT约2.695秒、整轮约3.158秒，峰值RSS观测862976KiB；GGML4线程、MLP4线程、CPU模式。1025token功能样本T1约55.28秒、T8约25.98秒。这些是本次功能测试的观测，部分与其他测试并行，不作为重复统计加速比、KV260速度或Jetson对比。

sidecar拥有数据140378112字节；原GGUF目标完整页丢弃并PROT_NONE，实测该部分RSS=0，边界共享页/非目标REPACK/启动峰值仍计入。72权重只加载一次，无每token导出、上传或整套重排，无BO。具体工作区和内存原始记录见REPORT.json、ready/records。

原`quality-v1/quality.json`保留：H0→S0平均KL约0.346134、S0→S1约0.376569、H0→S1约0.968640；旧短样例S1与最终v8数值相同已实证。该小样不代表广泛量化无损或临床质量；长KV修复改变非MLP浮点归约安排，不声称所有长上下文与旧轨迹相同。S2硬件误差未测、必须为null。

## 失败及更正均保留

- 原state-v1和F16诊断失败未删除；关闭单条tiled路径的隔离试验不是通过结论。
- `empty-repro-v6/report.json`保留native退出-11；测试脚本的退出0表示成功复现预期崩溃。`empty-repro-v7`同输入通过。
- `state-v6`、`extra-batch-v6`、`app-dev-v6`保留空输出崩溃相关失败；`extra-batch-v7`保留1025token全词表越限，不能因4个decode token碰巧相同判通过。最终v8重跑原输入通过。
- 首次node-analysis比较中的`conv_state_last/new_state`对应不同前缀长度，不可用作首token差异；更正明确列于root-cause-v2.json。首个根因脚本大写ID筛选为空已修为真实小写并增加非空断言；原文件保留，空结果未用于验收。
- 封存工具首轮在Windows默认GBK解码中文路径时失败；改为显式UTF-8后重试。原退出1日志保留，不涉及模型测试失败或数据删除。

## 命令、身份、恢复与下一步

完整实际argv、退出码及日志SHA256在本目录`commands.json`与`platform/qwen35/a05/evidence/continue-*.json`。本报告/commands生成命令及最终seal自身避免循环哈希，独立receipt另存。

关键命令（在已有WSL `/mnt/c/Patientqwen`；输出目录为实际原始目录，重跑必须换新目录）：

```text
python3 platform/ra02/build_queue.py submit --owner A --label a05-v8-attention -- /bin/bash /mnt/c/Patientqwen/platform/qwen35/a05/build_native_v8.sh
python3 platform/ra02/build_queue.py run-next                                      # 0
python3 platform/qwen35/a05/state_regression.py --output eval/qwen35/a05/state-v8 --binary /home/member-a/qwen35-a05/build-v8/qwen35-s1  # 0
/home/member-a/voice-a03/venv/bin/python platform/qwen35/a05/analyze_state.py --input eval/qwen35/a05/state-v8 --output eval/qwen35/a05/state-v8/numerics.json  # 0
python3 platform/qwen35/a05/additional_batch_tests.py eval/qwen35/a05/extra-batch-v8 /home/member-a/qwen35-a05/build-v8/qwen35-s1     # 0
python3 platform/qwen35/a05/app_eval.py --output eval/qwen35/a05/app-dev-v8          # 0
bash platform/qwen35/a05/voice_s1.sh eval/qwen35/a05/voice-s1-v8                    # 0
```

主程序SHA256：`965b8431e6d1a7134d66cbf4da8d7995ce071d16e8d2d47481a36d7c9f65f105`。
SP CPU库：`d46bd1cc785c56d718e7b2782ced73bd7b3ab9a3510177df0bb0bbeacf69ee90`。
sidecar manifest：`cdb2a04dbd95d426ea8967cda0adb219a769d3630107a2af72d6ddf2d5285688`。
全部依赖见`runtime-build-v8.json`；当前文件封存见`files.sha256.json`及`seal-receipt.json`。before与source-v6/v7/v8快照、旧库和失败目录保留，可按对应manifest恢复，不能把新库覆盖到历史构建目录。

分支`member-a/qwen35-a00-20261002`，基底commit `ed9df6c7152c908d512ecd1f871583182823e1eb`；本轮无commit或push，原脏树保留。使用llama-cpp技能约束固定源码审计与隔离构建，实际助手设置unknown，未切换或启子代理。

A06前置已具备：A04数学/权重/独立参考、A05真实1024↔3584及T≤8输入。未执行A06，等待阶段指令。后续必做：教师审核、独立300题、A08可靠性/长测、声学计时、ARM/PL/BOARD。P2仅为可选R1/R2和更多吞吐优化，不能把后续必做门禁降为P2。
