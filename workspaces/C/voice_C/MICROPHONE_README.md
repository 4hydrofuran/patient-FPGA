# C03 麦克风补充

2026-10-02 用户要求“加入麦克风”。现在可在电脑使用 Realtek 麦克风边录边识别，无需 A 的完整应用。采集在独立客户端中，语音 worker 的公共接口与职责保持原定义。

## 开始使用

在 PowerShell 中执行以下命令。看到 `RECORDING` 后开始说话，例如“这是一次麦克风测试。我没有发热，也没有咳嗽。”默认只录 10 秒，不会持续监听。

```powershell
& 'C:\vivado\KV260\workspaces\C\voice_C\tools\run_microphone.ps1'
```

可调整时间或仅查看设备：

```powershell
& 'C:\vivado\KV260\workspaces\C\voice_C\tools\run_microphone.ps1' -Seconds 20 -Countdown 10
& 'C:\vivado\KV260\workspaces\C\voice_C\tools\run_microphone.ps1' -ListDevices
```

每次运行创建新的 `evidence/c03_mic/manual_日期时间_随机后缀/`，不覆盖已有记录。终端显示中间识别文字与最后结果；中间文字只用于显示，最后只有 `asr_finish` 结果可以提交。`report.json` 保存最终文字、声卡采集状态、音量统计、延迟和错误；`trace.jsonl` 保存完整本地协议。报告与 trace 包含转录，按本地个人测试记录保管，不自动发送或外发。

原始音频只在内存和临时 spool 中出现。每块在 ACK 和 hash 核对后删除；失败时清理自有临时目录。没有录音文件长期保存，也不会自动加入 C00 学生录音数据集。要算 CER，需另行授权保存评测音频并人工核对逐字参考文字；建议测试句不是实际说话真值。

## 实际测试结果与边界

- 设备 0：麦克风 (Realtek(R) Audio)。支持本次请求的 16000 Hz、mono、PCM16。
- 第三次运行实际打开并启动设备，采集 10 秒 / 160000 个样本 / 50 个 200 ms 块，采集 hash、各块 ACK 与最终 hash 一致。
- 队列峰值 1，无队列溢出、无已检测到的原生缓冲耗尽；设备 reset/unprepare/close 成功，worker 正常退出，原始音频未保留。
- 用户随后确认“没有朗读，稍后自行测试”。本次最终文字为空；收到的是微弱非零音频，不能当作朗读成功、学生 CER 或短否定质量结果。
- 该次 chunk ACK 中位数 6.080 ms、最大 53.998 ms；块可用到发送最大 3.391 ms；显式 finish 到 final 19.014 ms。只有一次采集，不能据此给出稳定 p95，更不是人声结束或实际出声延迟。
- 原运行环境与独立麦克风环境的 99 项回归均通过，其中新增 10 项使用驱动夹具，不会打开物理麦克风。真实采集证据另记，未将夹具称为硬件测试。

真实证据为 `evidence/c03_mic/real_run_03/report.json`。早两次失败保留：第一次在隔离执行中 waveInOpen 返回 MMRESULT=1，采集为零；第二次在本机权限运行中 worker 读取依赖版本为 null，锁定检查失败，未打开麦克风。两种执行环境对原 .venv 的依赖元数据读取结果不同，底层原因未确定。

为避免修改原环境，使用相同 SHA256 的既有离线 wheel 建立 `.venv_mic`，版本仍为 numpy 2.5.3、sherpa-onnx / sherpa-onnx-core 1.13.8。没有升级依赖、联网安装或修改全局 Python/驱动。启动脚本优先使用这个环境。`tools/prepare_microphone_runtime.py` 只在目标目录不存在时创建，不会覆盖已有环境或历史安装日志。

## 实现与错误处理

`voicec/microphone.py` 用 Windows WinMM，16 个原生缓冲区、默认 32 块 Python 队列，由独立采集线程持续读取；识别等待不会直接阻塞采集。队列满或原生缓冲耗尽会明确失败，不静默丢音频。录制范围 0.2—60 秒，标准脚本每轮 1—60 秒，末块允许少于 200 ms。不做 AGC、VAD 剪切或自动端点提交。

WinMM 格式查询不录音，实际录制才调用 waveInOpen/start；只读取 dwBytesRecorded 中的有效 PCM。结束 reset 归还缓冲，再 unprepare/close；若驱动拒绝清理，报告错误并保留仍可能被驱动引用的内存，不能伪称已释放。实现参考 [Microsoft waveInOpen](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveinopen)、[waveInAddBuffer](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveinaddbuffer) 和 [录音生命周期](https://learn.microsoft.com/en-us/windows/win32/multimedia/managing-waveform-audio-recording)。

若打开设备报错，先查看本轮 report/stderr。确认所选设备连接可用及 Windows 的麦克风权限后再人工运行；本实现没有自动改隐私设置或驱动。如果有正常朗读但结果为空，应记录真实文字、设备与音量情况后排查，不能通过填入预设句子冒充识别。

C02 的人工盲听、C01 的学生录音质量、权重分发许可、板端与实际扬声器出声仍待完成。本补充不等于 C04 最终质量冻结或默认系统采用。
