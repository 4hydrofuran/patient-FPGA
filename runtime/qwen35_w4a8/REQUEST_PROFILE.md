# N02请求级分账（私有诊断扩展）

不改变SP_LINEAR_V1、量化数学、模型/llama提交、线程和图调度。原默认部署manifest仍指向已封存旧构建；N02只生成隔离的可验证构建，不自动替换运行中的版本。

在原每轮JSON请求中可添加：

```json
{"profile": true, "profile_detail": false, "session_id": "local-test", "session_epoch": 1}
```

`id`沿用原请求ID。默认`profile=false`；`logits_mode`仍默认`final`。`request_profile.phases`按prefill/decode分账，不同请求开始时全部清零。`cpu_counters`是两次请求边界读数之差，旧`bridge.cpu_compute_ms/service_ms`仍是last-op，旧`cpu_run_count`仍是lifetime，新增process_total明确累计口径。

`profile_detail=true`才序列化phase/layer/op/N/K/T、首末execution序号与调用/失败统计；普通计时只发聚合账，不逐节点写文件。`diagnostic_report=true`才执行原smaps/全部权重统计（diagnostic_dir也会启用）；性能模式这些未采样字段为null，不填0。`state_fingerprint=true`仅供状态控制对照，序列化真实混合状态后取摘要，不纳入性能样本。

## 不重复相加的层级

```text
llama_decode墙时
├─ CPU graph实际执行墙时
│  ├─ MLP custom回调墙时
│  │  ├─ SP_LINEAR完整调用墙时（验证、INT32/FP32计算、输出拷贝等）
│  │  ├─ 输入gather、A8量化、激活缓存拷贝、图输出拷贝
│  │  └─ bridge其他开销
│  └─ 非MLP CPU graph墙时（含其他算子、后端计划与线程调度/屏障）
└─ CPU graph外的图准备/调度墙时
```

非MLP不是用整个prefill减一个last-op推算。`request_profile.cpp`通过Linux ELF符号插入，包裹锁定ggml的现有`ggml_backend_graph_compute_async`，只在实际执行前后读钟。已检查对应`ggml-backend.cpp`委托`iface.graph_compute`，CPU后端同步返回`ggml_graph_compute`结果；不新增同步、不拆节点、不禁用融合、不读输出参与计算。仅同步CPU语义已验证；非CPU身份、未截获实际graph调用、负残余均标计时账无效。

MLP计时位于`Bridge::compute`（不是建图函数），多个线程的时间不相加。新过程计数器只累计原有计时值；INT32/FP32源码不重结合，不改变缓存key、bias、权重读取和输出复制。

## 可复现构建

```sh
cmake -S /mnt/c/Patientqwen/runtime/qwen35_w4a8 \
  -B /home/member-a/review-n02/build-v1 -DCMAKE_BUILD_TYPE=Release \
  -DROOT=/mnt/c/Patientqwen \
  -DLLAMA_SOURCE=/home/member-a/qwen35-a05/source-v3 \
  -DLLAMA_BUILD=/home/member-a/qwen35-a05/llama-build-v4
cmake --build /home/member-a/review-n02/build-v1 --parallel 2
```

固定库/资产sha256由测试前检查、实际产物hash及命令收据记录。首次四个自然输入对照旧构建，再做同样四个输入×三次开/关交错，teacher token轨迹来自旧真实生成，不是预写答案。

应用`Service.turn`另外写`attempts.jsonl`的ARRIVAL/FINISH记录，涵盖参数拒绝、BUSY、维护等待/失败、正常轮次和取消超时。旧input_submitted仍为维护后轮内起点，新arrival在入函数处，不改写旧字段含义。缺time namespace时记录null/errno及仅本进程时域，不宣称跨进程可比。

详细证据：`evidence/review_tasks/N02/20261008-v1/`。历史N01缺失的配置hash、最后一条分组和维护归属依然缺失，本功能不回填历史记录。所有BOARD/ARM实际运行仍NOT_TESTED。
