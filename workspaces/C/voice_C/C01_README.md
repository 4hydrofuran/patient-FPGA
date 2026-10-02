# C01：真实中文识别与本机线程比较

2026-10-02（北京时间）。真实中文 ASR 已接入并实际运行；状态 `PC_ENGINEERING_COMPLETE_QUALITY_AND_LICENSE_PENDING`。交付可以接收 WAV 并返回实际模型转录；学生口语、医学语义、KV260 和最终候选替换验收尚未通过。

## 模型、依赖和许可

采用任务指定的 Zipformer-small-CTC INT8 中文模型。[官方说明](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/online-ctc/zipformer-ctc-models.html) 对应作者的 [ONNX 仓库](https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01)，固定 revision `a5f60fe00dcfbaf68fcc1c6b5cf53061e144d6da`。权重 26,342,340 字节，SHA256 `68c9c943840f7d9cf3e8a4970ba50f404feb5277f611fa82b7e72267786fa84a`；词表 SHA256 `6fed8c6c248516f38e7faa19404b57413e8ce259f1cbc1fa4aebc86eac32fdfd`。大文件与发布方 LFS SHA256 匹配。bbpe.model/来源说明也已保留；实际 greedy CTC 运行只读取权重与 tokens。

独立 Windows AMD64 / Python 3.12.14 venv 固定 sherpa-onnx 1.13.8、sherpa-onnx-core 1.13.8、numpy 2.5.3。三个 wheel/hash 锁、实际安装日志和 API 签名见 assets/wheels、requirements-c01.lock.txt、evidence/c01/runtime.json。原始 checkpoint 声明 Apache-2.0，ONNX 仓库未单独声明许可。**ONNX 导出与外发许可 REVIEW_PENDING**，用户答复“暂无补充，先保留待确认”。依赖及原始模型声明不能自动充当导出权重外发授权。本次未发布 zip 或向 A 发送文件。

安装和检查在本目录执行：

```powershell
Set-Location 'C:\vivado\KV260\workspaces\C\voice_C'
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& .\.venv\Scripts\python.exe tools\install_c01_offline.py
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

安装工具调用 bundled Python 的 pip，只写本目录 .venv/Lib/site-packages，使用 --no-index / --require-hashes。本次已存在目录会提示，不强行覆盖或全局升级。全新电脑/ARM64 的独立安装包属于 C04，尚未完成。

## 数据与处理

Windows 中文声音可枚举，但 System.Speech/SAPI 实际合成均失败；失败日志/文件保留，未生成成功的本地合成语音。转用 Google 发布、CC-BY-4.0 的 [FLEURS-R](https://huggingface.co/datasets/google/fleurs-r)，revision `c621c0b7b569dcebcd50273a187a35d1a1fc895f`。从中文 dev.tsv 按识别前固定规则选择 14 个不同音频、12 种文字，包含否定/数字/时间/频次/症状/术语；规则与完整 dev 清单已保留。没有读取 test 音频或 C00 最终脚本进行调参。

FLEURS-R 是对原始 FLEURS 朗读语音进行模型修复的 24 kHz 数据，处理见 [原论文](https://www.isca-archive.org/interspeech_2024/ma24c_interspeech.pdf)。保留原 WAV，离线通过带低通的采样率转换生成 16 kHz 输入；转换工具验证时长、直流幅度、通带与高频抑制。24 kHz 初始输入被严格接口拒绝的日志、原文件也保留。它不是未经处理的 FLEURS、学生问诊或完整数据集评测。

Runtime 不重采样、去噪、AGC 或裁剪；PCM16 除以 32768 转 float32，记录原始 frames、时长、哈希、静音、削波和过短警告。参照锁定 [官方解码示例](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/python-api-examples/online-decode-files.py)，尾部加 660 ms 零采样仅用于冲刷，计算耗时包含此成本，输入时长不含补零。每请求新建识别状态，模型常驻；未知置信度恒为 null。

发布方文字未经本地人类听写核验；TSV 不提供说话人 ID，保持 null，不宣称说话人隔离已证明。自己的 48 条录音脚本、实际参与者、授权、转写仍未完成，真实学生 CER=null。公开音频的使用依据为 CC-BY-4.0，未伪造个人同意记录。署名、修改说明、来源、原始/转换后 SHA256 在 data/c01_public/manifest.jsonl、ATTRIBUTION.md 和 archive.lock.json。

## 测量结果与错误

每条音频重复三次、固定随机顺序；三个线程配置各 42 次，共 126 次。每种配置使用新 worker，并单独记录一条完整预热。全部实际运行成功、无超时；不同线程及重复间转录一致。

| 推理线程 | 次数 | compute p50 / p95 | RTF p50 / p95 | worker 峰值 |
|---|---:|---:|---:|---:|
| 1 | 42 | 759.2 / 1394.7 ms | 0.0621 / 0.0772 | 146.6 MiB |
| 2 | 42 | 592.0 / 1145.0 ms | 0.0464 / 0.0588 | 146.4 MiB |
| 4 | 42 | 822.1 / 1619.5 ms | 0.0668 / 0.0902 | 146.7 MiB |

唯一开发配置 configs/asr.selected.json 选 2 线程、CPU、无偏置 greedy_search，按输出一致、无运行失败条件下本机 p95 最低选择。INT8 属起点模型内部量化，本阶段没有改量化、添加词典或做答案缓存。计时包含 WAV 读取、特征及解码，不含模型首次加载；加载、首条完整解码和进程生命周期峰值内存另记 hello.json / warmups.json。输入长 8.88—27.12 秒，完整音频计算 p95 不是用户端点尾延迟或实际首音。线程依次测试、共享主机 CPU、三次重复：仅开发比较，不能映射 A53 或宣称显著改善/默认替换。

严格字面 CER：148/606 = **24.42%**，以 14 个音频首轮输出计，不将重复次数算成额外质量样本。英文括注、人名、数字、难句及错误未删除。关键项字面计数不一致：数字 8/8；否定 0/4、时间 0/2、频次 0/2、症状 0/2、术语 0/2。后五类的 0 不表示语义正确；数字的阿拉伯/中文写法差异未做逆文本归一化。错误分析另标注表示差异，主 CER 和原始输出不变；语义审核仍需人类。

还实际测试静音、20 ms 全削波、1 秒削波，均返回空转录和对应警告。这三条是合成边界输入，不是语音质量样本，也不证明所有无效声学输入都不会误识别。

实际 CTC 工厂签名没有 hotwords_file 参数，官方 Zipformer2 CTC 分支用 greedy_search。本候选未配置热词、通用术语偏置、FST 或同音替换，不把参考文字输入模型。非协议的热词/参考文字字段拒绝。hello 的 real_asr=true、real_tts=false、streaming_asr=false；底层流式模型不等于 C03 公共流式接口已完成。

## 复现与证据

```powershell
# 持久进程；spool 使用公开工程音频目录
& .\.venv\Scripts\python.exe -m voicec.worker --spool .\data\c01_public --asr-config .\configs\asr.selected.json
```

输入 stdin JSONL（输出只为 stdout JSONL）：

```jsonl
{"api_version":1,"request_id":"h1","op":"hello"}
{"api_version":1,"request_id":"r1","op":"transcribe","session_id":"c01.public.001","wav_path":"c01.public.001/in.wav","language":"zh"}
{"api_version":1,"request_id":"s1","op":"shutdown"}
```

重跑比较必须使用新目录，保留原数据：

```powershell
& .\.venv\Scripts\python.exe tools\compare_c01_threads.py --output .\evidence\c01\comparison_reproduce
```

实际个人录音完成后用 tools/benchmark_asr.py，必填 --manifest / --audio-root / --asr-config / --output。它要求授权、音频哈希、人工转写；当前 NOT_COLLECTED 计划不能产生学生质量报告。

49 项检查全通过、0 跳过：原 35 项及新增 14 项。命令/退出码/原始日志在 evidence/c01/first；全部转录、编辑距离、关键项、计时、内存在 thread_comparison/raw.jsonl，摘要 report.json；初始化和预热单列。边界 edge_inputs/report.json，依赖 runtime.json，错误分析 error_analysis.json，历史完整性 history_integrity.json，最终清单 artifact_manifest.json。

推理在默认禁止网络连接的沙箱中使用本地文件；额外 Python socket 连接禁止检查通过。未声称物理断网重启或所有原生库网络行为已审计，C04 完整断网复现未执行。当前 HLS 域不适用；ARM64、BOARD、音频设备、实际首音、整机比較和能耗均 NOT_TESTED。助手实际选项未核验；未声称切换。

下一步保留基线，采集获授权、分离说话人与句型的学生开发/最终录音，核验转写，补小数、短否定、完整医学术语、问题句型和噪声，确认 ONNX 导出许可。C02/C03/C04 尚未执行，本次未下载 Matcha/Vocos、未上板、未修改旧病例/评分/冻结问题。
