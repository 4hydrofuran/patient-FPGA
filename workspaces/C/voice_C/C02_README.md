# C02 短句合成：电脑工程完成，人工发音评测待办

2026-10-02，北京时间。当前使用 Matcha 中文 Baker + Vocos，返回真实 22050 Hz、单声道 PCM16 WAV。
入口为现有持久 SP_VOICE_V1 JSONL worker；输入短句保持原文，记录 UTF-8 SHA256。
模型驻留，输出音频每次重新生成；语速、长度、噪声、暂停参数均固定为 1.0，不提高语速或缓存答案。
词表、词典和 phone/date/number FST 使用发布者原文件，按实际摘要锁定，没有借用旧病例答案调参。

正式开发测量 138 次全部成功：1/2/4 线程各 42 次，另有 2 线程原生两句批处理 12 次探索比较。
当前推荐的电脑配置为 `configs/tts.selected.json`：2 线程，每个原生批次最多 1 个句段。
2 线程合成耗时 p50/p95/max 为 438.7/722.8/795.9 ms，RTF 为 0.1277/0.1512/0.1599；峰值内存约 252.8 MiB。
RTF 是合成耗时除以音频时长，例如 0.15 表示生成 1 秒声音约需 0.15 秒。
单句组 30 次在客户端收到完整 WAV 的 p95 为 516.2 ms；所有短答的客户端 ready p95 为 727.4 ms。
内部 callback p95 约 450.0 ms 只是诊断，未通过公共接口交付，不是首句可播放时间或实际出声时间。
原生两句批处理可能更快，但音频时长也变化，且只有 12 次探索测量；在真人核对前保留批次 1。

现有 C00/C01 的 49 项检查加 C02 的 18 项检查，共 67 项通过，0 跳过。
真实 ASR+TTS 同进程回归保留了选定旧音频的原转写；取消/reset 丢弃迟到音频，保留调用者文件。
该同进程检查使用 1 线程 TTS 做功能验证，峰值约 299.3 MiB；不是选定 2 线程组合的性能基准。

在本目录运行：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -m voicec.worker --spool spool --asr-config configs/asr.selected.json --tts-config configs/tts.selected.json
```

第二条命令启动持久 worker，从 stdin 接收一行一条 JSON，stdout 仅输出协议。
省略 `--asr-config` 可只启用 TTS；省略两者保持 C00 契约模式。TTS 不读取 Qwen、病例、评分或其他成员工程。
模型与依赖均在独立工作区；本阶段没有升级 C01 的依赖。
输入最多 160 字；调用者须提供已经批准的完整短句，worker 不替主应用做事实检查。

请求示例（启动后逐行输入）：

```json
{"api_version":1,"request_id":"hello-1","op":"hello"}
{"api_version":1,"request_id":"tts-1","op":"synthesize","session_id":"demo","text":"我没有发热，也没有咳嗽。","output_dir":"demo/out"}
```

结果返回相对于 spool 的 `wav_path`。先读取/播放/复制结果，再 reset 或 shutdown：worker 会删除自己的临时音频。
测试保留的音频在 `evidence/c02/benchmark_final/audio/`；匿名试听音频在 `listening/c02/audio/`。
当前只有开发数据，没有完成最终独立测试。

首次复现依赖用 C01 已锁定的离线安装材料；不共享整个 venv。运行时只读本地资产，没有下载函数。
模型资产取得命令：`.venv/Scripts/python.exe tools/acquire_c02_assets.py`（需要公网，已有文件核对摘要）；
性能重跑：`.venv/Scripts/python.exe tools/benchmark_c02.py --output evidence/c02/new_run`。
不要覆盖已有测量或盲听表，也不要重新执行会改写 C00/C01 历史 manifest 的阶段脚本。
若重跑性能，必须保留所有失败输入、固定文本、语速、音量政策、预热和冷启动记录。

实际发现并保留的缺陷：

- 第一次下载连接被重置；重试成功，原日志保留。
- 第一轮 TTS-only worker 超时，诊断显示工作线程首次加载 NumPy 停在 DLL 模块创建；启动时先加载 NumPy 后通过。
- Python sid/speed 重载使用 GenerationConfig 的默认暂停比例约 0.2；现在显式传入 1.0。早期 138 次试跑保留在 `benchmark/`，不用于最终配置结论。
- 上游 Python 回调文档与 Matcha 实测相反：非零继续、零停止；两句实测已保存。单个原生批次可能不能立即打断，cancel_pending 与丢弃策略如实回报。
- 原词典有四条 `shei2` 未收录于词表，加载时有警告，未静默改词典；单独记录于 `comparison_analysis.json`。
- 辅助 ASR 对“心悸”“心电图”“支气管炎”等转写有不一致；数字常转写成汉字。这只能提示复核，不能判断 TTS 发音正确率。

真人试听按用户要求仅准备了 [待填写盲听表](listening/c02/待填写盲听表.md)、14 条匿名音频和审核者参考键。
已听 0 条，可懂度、自然度、否定/数字/漏读/多音字错误均为 null，不能称音质验收完成。
Baker 模型卡注明训练数据仅供非商业使用，Baker/Vocos 导出权重许可均待确认；目前没有向 A 发送或外发权重。
流式 API、ARM64、KV260、扬声器首音、整机时延、2 小时稳定性与能耗均未测。

完整结果：`evidence/c02/verification.json`、`benchmark_final/report.json`、`comparison_analysis.json`、`commands.json`。
历史完整性：`history_integrity.json`；本阶段审计摘要：`artifact_manifest.json`。
后续 C03 可继续协议与调度工程，发音质量与 C01 的授权学生录音评测仍须独立补齐。
