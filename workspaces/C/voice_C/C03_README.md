# C03 流式识别、端点与服务调度

当前实现显式启用的 SP_VOICE_V1 流式 ASR。继续使用 C01 的固定 Zipformer-small-CTC INT8 权重、2 线程配置和 C02 的锁定依赖，未换模型、词典或病例内容。
用户本次不授权麦克风录音，因此只做公开开发音频的电脑工程重放；没有打开麦克风或扬声器。

## 运行方式

在本目录运行：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& .\.venv\Scripts\python.exe -m voicec.worker --spool spool --asr-config configs/asr.selected.json --tts-config configs/tts.selected.json --stream-config configs/stream.selected.json
```

只有指定 `--stream-config` 才启用流式能力；旧 ASR/TTS-only 启动方式保持非流式能力标识。
`hello` 返回 streaming_asr=true、optional_ops 和实际模型/端点/线程配置。
stderr 只放诊断，stdout 只放 UTF-8 JSONL 协议。

## 请求与提交规则

1. `asr_begin`：提供 session_id、sample_rate=16000、channels=1、format=pcm_s16le，取得 stream_id。
2. `asr_push`：提供 stream_id、从 0 连续递增的 seq 和会话目录中的 pcm_path。文件为原始小端 PCM16 字节，不带 WAV 文件头；每块最多 3200 个采样点，即 200 ms。
3. 收到 consumed ACK 后，调用者才可删除或复用该块文件。每块摘要和消耗的采样点数保存在响应中。
4. partial 是 event，只供界面显示，final=false、display_only=true、commit_allowed=false。主应用不得将 partial 送入病例/评分/LLM。
5. 最后一个 push 可带 final=true，表示不再接收输入；它不是可提交的最终转写。调用 `asr_finish` 才返回唯一 final=true、commit_allowed=true 的结果。
6. finish 后再 push 或重复 finish 均拒绝；reset 后旧 stream_id 按旧 epoch 拒绝。

示例：

```json
{"api_version":1,"request_id":"begin-1","op":"asr_begin","session_id":"demo","sample_rate":16000,"channels":1,"format":"pcm_s16le"}
{"api_version":1,"request_id":"push-1","op":"asr_push","stream_id":"替换为返回的编号","seq":0,"pcm_path":"demo/chunk.pcm","final":false}
{"api_version":1,"request_id":"finish-1","op":"asr_finish","stream_id":"替换为返回的编号"}
```

输入的幅度只按 PCM16/32768 转换，不使用能量门限删块，不裁剪否定或停顿。结束时加入 C01 相同的 660 ms 计算尾部静音以刷新解码器；原音频时长和摘要不包括该刷新填充。

## 端点和调度

使用模型原生 CTC 端点检测，开发候选的有声后静音门限为 0.8/1.2/1.6 秒；当前 1.2 秒是提示配置。
原生端点有可能在录音中间触发，不能据此证明说话已经结束。目前仅回报 endpoint_detected 提示，不自动提交 final、不 reset 原生识别状态、不丢弃后续 PCM。
因此暂停后继续说话仍属于同一条流；正式结束由主应用调用 finish。自动结束的实用门限仍需授权真人录音和实际麦克风验证。

同一时刻只有一个原生计算任务，队列最多 2 项。一个活动 ASR 流占用语音服务，期间 TTS、整文件 transcribe 和另一个 begin 返回 HALF_DUPLEX_BUSY。
这验证的是 worker 计算半双工；声卡播放/录音互斥和回声处理由主应用负责，尚未测试。
cancel 对活动流标记 pending；若原生计算不能立刻中断，在计算边界结束并丢弃迟到 partial/final。
reset 同样使旧流失效，只清理自有输出，不删除调用者的 PCM 文件。
每流最多 60 秒、1024 块；每进程最多 64 个流标识，15 秒空闲租约释放原生流；原有 4096 请求和 64 会话限制仍保留。
坏 PCM 会终止该流，已接收的后续排队请求返回 STREAM_ABORTED，避免输出缺块文字。调用者须重新 begin。

## 独立客户端与复现

`tools/stream_c03_file.py` 读取 16k mono PCM16 WAV，在受控临时目录分成原始 PCM 块，保存完整协议 trace。

```powershell
& .\.venv\Scripts\python.exe tools\stream_c03_file.py --wav <已授权或许可明确的16k音频路径> --output evidence/c03/new_manual_run --paced
```

使用 --paced 时，第一块在约 200 ms 后送出，此后按音频采样点对应的实际时间送块；省略该参数只是加速工程重放，不能称实时音频输入。
个人录音授权依据可用 --consent-reference 记录；客户端不会自行认证授权或把本地录音上传。
性能重跑 `tools/benchmark_c03.py` 的固定输出目录必须未存在；不要覆盖既有原始记录。
回归使用：

```powershell
$env:VOICE_C_TEST_EVIDENCE_DIR=(Join-Path (Get-Location) 'evidence/c03/new_selftest_run')
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

C02 测试写入目录已改为可配置；默认输出到 evidence/selftest_latest，避免再次覆盖历史阶段探针。

## 证据与限制

实际测量、通过数量和耗时见 `evidence/c03/verification.json`、`benchmark/report.json`、`edges/report.json`。
完整 trace 保存每次 request、accepted、partial、consumed ACK、唯一 final、控制错误与 shutdown。
按原时长的公开录音重放不是现场麦克风；公开恢复语音与合成短否定也不是学生质量验收。
文件末尾到 final 的耗时不等于真实说话结束到 final 的尾延迟，缺少真人语音结束标注和声卡实测时保持该区别。
C01 授权录音质量、C02 人工盲听、模型外发许可、ARM64、KV260、物理首音和整机稳定性仍待完成。

本次首次回归发现并已说明：旧 C02 自测脚本重写了 combined_regression.json 与 real_tts_cancel.json 两份探针。原摘要在 C02 manifest 中保留，原完整内容未恢复，不伪造还原。
正式 C02 的 138 次测量、WAV、盲听表和资产保持原内容；事件详情见 `evidence/c03/c02_probe_overwrite_incident.json`。
旧 C00/C01/旧版 C0/C1 的实际测量证据保持原内容，后续测试输出写入 C03。
