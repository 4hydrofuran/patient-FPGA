# 成员 C 离线语音模块：当前 C04 工程候选

当前已冻结一个候选配置，完成 103 项工程回归、30 次新 worker 冷启动、200 次语音模块循环，并生成 C_pc_candidate_v1.zip；最终 zip 独立解压/离线安装/49 项工程检查及真实 ASR、流式 ASR、TTS 自测均通过。包不含模型资源或私人录音；正式真人质量、外发许可、物理断网/OS 重启和板端仍待验收。说明见 [C04_README.md](C04_README.md)，交接 [C04.md](../docs/handoffs/C04.md)，候选 [C_pc_candidate_v1.zip](../releases/c04/C_pc_candidate_v1.zip)。麦克风操作见 [MICROPHONE_README.md](MICROPHONE_README.md)，用户已确认此前识别问题是设备原因，本轮没有新增录音。

显式传入 `--asr-config configs/asr.selected.json` 加载固定 Zipformer-small-CTC INT8 中文模型；`--tts-config configs/tts.selected.json` 加载固定 Matcha 中文 Baker + Vocos。两者的当前电脑开发配置均为 2 个推理线程。添加 `--stream-config configs/stream.selected.json` 启用 asr_begin/push/finish；省略它时仍报告非流式。未加载真实模型时保留 C00 CONTRACT_TEST 模式。依赖沿用 C01 锁定版本，C02/C03 没有升级依赖。

当前回归：在本目录使用 `.venv/Scripts/python.exe -m unittest discover -s tests -v`（当前 103 项，麦克风检查使用夹具，不会录音）。测试探针默认输出到 `evidence/selftest_latest`，也可用 `VOICE_C_TEST_EVIDENCE_DIR` 指定新的本轮目录。C03 首次回归曾重写两份 C02 自测探针，详细事件如实记录；C02 正式性能/音频/盲听保持原文件。**不要运行 tools/verify_c00.py 或旧阶段 finalize 脚本覆盖历史证据。**

下面内容记录 C00 完成时的历史框架及命令，不表示当前依赖仍仅有标准库；C00 原始证据和 48 条待采集录音计划保持不变。

## C00 历史说明

当前交付：**PC_CONTRACT_ONLY**。已完成SP_VOICE_V1框架、独立客户端、录音计划、授权/盲听空白表和指标工具；没有ASR/TTS模型、授权录音、真实语音质量或板测成绩。用户确认“暂时没有，先完成框架和录音计划”。

## 快速验证

在本目录执行（独立Python 3.12.14虚拟环境，无第三方依赖）：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& .\.venv\Scripts\python.exe tools\verify_c00.py
```

首次环境创建命令为bundled Python的`-m venv --without-pip voice_C/.venv`，include-system-site-packages=false；没有修改全局Python或安装语音依赖。源码可在Python>=3.10环境使用，当前只实际测试了Windows/Python 3.12.14。

## 实际具备的内容

- 持久本地worker：JSONL stdin/stdout，UTF-8，诊断stderr；支持hello、transcribe、synthesize、cancel、reset、shutdown的请求边界。
- 默认未配置引擎：有效WAV会报告MODEL_NOT_CONFIGURED，不返回伪造转录；默认TTS同样报引擎未配置。
- 显式`--contract-test-tone`仅输出440Hz短测试音，标NON_SPEECH_TEST_TONE和CONTRACT_TEST，绝不能当作语音合成。hello声明real_asr=false、real_tts=false、streaming_asr=false。
- 单个处理线程、最多2个排队任务；4096个请求ID/64个会话上限后明确拒绝，重启建立新实例。ID在同一进程不复用。
- 正在运行的不可中断任务取消时返回cancel_pending=true、stopped=false，丢弃迟到结果；reset递增epoch并丢弃旧结果。
- 受控spool及会话前缀：拒绝绝对路径、../、反斜杠、ADS、符号链接、NTFS junction/reparse point、Windows保留名及含糊路径。输出独占新文件，不覆盖已有文件。
- reset/shutdown仅删除本worker记录的输出文件；不递归删除目录，不删除主应用输入、其他会话或用户文件。spool应由受信主应用/worker独占写入；此框架不声称防御同权限进程恶意并发替换文件的所有竞态。

worker不导入或读取病例、评分、Qwen、FPGA或A/B工程，不调用网络、云端、麦克风或扬声器。原始音频/正文不写默认诊断日志；测试trace只用明确的工程文本及静音/测试音。

## 协议与运行

```powershell
& .\.venv\Scripts\python.exe -m voicec.worker --spool .\spool
```

输入示例（相对路径必须以对应session_id为第一目录）：

```jsonl
{"api_version":1,"request_id":"hello-1","op":"hello"}
{"api_version":1,"request_id":"asr-1","op":"transcribe","session_id":"s1","wav_path":"s1/question.wav","language":"zh"}
{"api_version":1,"request_id":"tts-1","op":"synthesize","session_id":"s1","text":"已通过业务事实检查的短句。","output_dir":"s1/out"}
{"api_version":1,"request_id":"cancel-1","op":"cancel","target_request_id":"tts-1"}
{"api_version":1,"request_id":"reset-1","op":"reset","session_id":"s1"}
{"api_version":1,"request_id":"stop-1","op":"shutdown"}
```

响应回显api_version/request_id/op/type，字段置于响应顶层。异步语音操作先发accepted事件，再返回result/error；取消/重置后的迟到结果不发终态答复。cancel用新的request_id关联自身响应，target_request_id指定原任务；这是本实现明确的请求字段，不改动公共契约文件。客户应依取消响应/epoch忽略旧accepted事件，不能等待已丢弃任务继续返回正文。

JSONL每行最大32768字节，文本2048字符，音频10MiB/60秒；ASR mono PCM16 WAV、16000Hz。坏JSON、重复字段、NaN/Inf、错采样率和损坏WAV明确报错。测试客户端voicec/client.py独立启动worker，不使用shell执行输入文字。

## 录音与评测

data/录音计划.md包含48条独立新脚本：开发24、最终测试24；六类为普通话、否定、数字、时间、问句、术语。未复用旧324题或其参考答案。预留说话人组不是已经招募的真人，真实说话人编号、授权、音频/hash和转录审核仍为空。

复制recording_plan.jsonl填写自己的采集副本；实际转录需替换为逐字核对后的reference_text，而非假设朗读完全等于脚本。收集之后按实际说话人、句型来源、原音频hash校验隔离。字符/来源检查不能证明语义完全独立，最终录音仍需人工审计。授权表authorization.template.json不代表已授权；tts_listening.template.jsonl的12行也没有听众或分数。

voicec/metrics.py提供CER、字面关键短语保留检查、RTF/ready/内存字段及独立人工盲听意见采集。数据和计算规则在data/metrics_definition.json。无完整结果时full_set_cer=null，另报已观察CER、覆盖和缺结果；不让只成功几题冒充完整成绩。关键短语计数不能证明否定语义正确，仍需人工检查。

tools/benchmark_asr.py在实际录音、许可及人工转录校验后才收集识别结果；当前引擎未配置，会明确拒绝产生语音质量成绩。禁止用--allow-contract-fixtures给真实结果“补标签”。TTS完整WAV ready不是流式首块，更不是用户听到首音；当前首块/物理首音均null。

Windows内存采集使用[GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo)及[PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters)，单位为字节；峰值是整个worker进程累计峰值，不是单个模型的增量内存。Linux/macOS代码已准备，尚未在这些环境执行。

## 证据与限制

evidence/c00/verification.json保存实际命令/退出码，unittest.log是测试原文，contract_demo.json及protocol_trace.jsonl是实际子进程协议烟测。artifact_manifest.json绑定交付文件。第一次手动测试跳过1项Windows符号链接权限检查，已用真实junction补测至无跳过；初始摘要保留在initial_check_summary.json。

初次短操作使用GetTickCount64单调时钟，0.015625秒分辨率导致0ms读数；初始结果和时钟信息保存在initial_timing_observation.json。已统一改用perf_counter高精度单调计时，不调整/编造数据。

此阶段完成框架与计划，真实录音/授权待采集；ASR质量由C01实际执行，TTS由C02执行。C00不替代后续真实语音、aarch64或KV260验收，不创建C04候选包、不向A发送材料。
