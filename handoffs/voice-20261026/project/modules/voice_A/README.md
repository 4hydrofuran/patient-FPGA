# A03 默认离线语音（PC / WSL）

当前A03电脑离线功能基线已收口，不是KV260或完整产品质量验收。断外网冷启动WAV闭环、授权麦克风、原句确认及单例人工听辨已有真实证据；广泛语音质量、声学回采和异常设备可靠性仍待后续验证。病例/未知策略未获教师审核，正式教学关闭。最新入口：`eval/qwen35/a03/closeout-v1/REPORT.md`。

## 实现与固定资源

- `worker.py` 持久 JSONL；stdout 只输出协议，含原生库在内的诊断进入 stderr。ASR/TTS 各加载一次，CPU 各 2 线程；主应用 Qwen CPU 3 线程。运行时不联网、下载或选候选。
- sherpa-onnx 1.12.40 / commit `d795ccd164bd2360ffda6c3431b1316e2c898be2`。ASR 是 2025-04-01 中文 Zipformer-small-CTC INT8；TTS 是实际下载的 Matcha Baker `model-steps-3.onnx` + Vocos 22k。完整 SHA256、来源和许可见 `resources.lock.json`。
- 包的归档 hash 才是冻结身份，不能只凭文件夹日期；Matcha release 资产元数据可能晚于模型名。BSC-LT Vocos 权重 Apache-2.0 与 Vocos 代码 MIT 分开。Matcha/Baker 数据明确有非商业限制，当前禁止自动发布权重；不构成竞赛/商用/再分发法律许可。
- 安装隔离于 `/home/member-a/voice-a03/venv`；私有 Pulse 依赖位于 `/home/member-a/voice-a03/audio-libs/root`，没有系统安装或替换旧运行库。pip 实际 wheel/间接依赖及 hash 见 `eval/qwen35/a03/pip-install.json`，Ubuntu deb 见 `audio-packages-v2.json`。这是 PC x86_64 包，不是 ARM64 包。

## 协议与边界

沿用 `contracts/qwen35/voice_v1.json`，未改公共文件。hello / transcribe / synthesize / cancel / reset / shutdown 及能力位下的 asr_begin / asr_push / asr_finish 均实际测试。

`cancel` 使用目标原 request_id，op 为 cancel；取消确认与原请求终止结果分别返回。不能把 cancel_pending 当作原生计算已经停止。reset 递增 session epoch，旧请求/流无效，迟到 TTS 删除而不交付。单并发、4 作业队列、8 会话、4096 请求上限，达到请求上限须维护窗口重启，不允许静默接收无限工作。

输入 mono PCM16 / 16000 Hz / 最长30秒。流块200ms（6400字节），seq严格有序；ack后主应用才删块。尾块零补齐，不删除源静音；ASR完成另加300ms recognizer flush。输出22050 Hz，固定 sid=0、speed=1.0、silence_scale=1.0。默认按键说话，不因端点对比挑最好看的一项切默认。

spool独占、限制64MiB/512文件，拒绝绝对路径、跨会话、链接和越界；reset只删worker自己生成的音频。不是防御同一OS用户恶意竞态的安全沙箱。麦克风入口用 `/dev/shm` 临时spool；合成测试音频为了可重复验证保留且注明来源，不能当真人数据。

主应用 `system_qwen35/app/audio_adapter.py` + `voice_loop.py` 控制半双工/epoch/录音播放。partial仅显示；只有final进入业务。完整首句通过事实检查后才TTS。音频ready、播放提交、播放API drain分别记录；声学起点/首次有效声音均null，无回采不报实测出声。

ASR不提供校准置信度，原值保留null。自动闭环仅对来源明确且原始ASR与已知合成文句逐字相同（忽略标点）的fixture做内部确认，让Qwen路径可测；不改转录，不把病例真值用于纠错，不是人工确认。评分仍待审核、不得计分。麦克风不使用此捷径，未确认的真实转录保守澄清。原句YES交互已在授权第一/第四轮实际使用；第四轮真实Qwen回答通过事实检查且用户反馈清晰。仅证明小样本功能，不宣称自然问诊质量已全面通过。

## 重跑（WSL，输出目录必须全新）

```sh
cd /mnt/c/Patientqwen
python3 platform/qwen35/a03/protocol_eval.py eval/qwen35/a03/protocol-manual-new
bash platform/qwen35/a03/offline_loop.sh eval/qwen35/a03/offline-manual-new
```

第二条使用新user/network namespace，外网不可达，但保留本地WSLg Unix音频socket，不改变宿主网络。固定WAV并非实时麦克风输入，不能把文件快速送入ASR的耗时称为真实说话端到端时延。四个样本及失败不删改。

麦克风已按用户授权完成小样本测试；本次收口未新增录音。**后续仍仅在用户明确同意录本人合成句后**，由用户在WSL交互终端执行：

```sh
cd /mnt/c/Patientqwen
audio_prefix=/home/member-a/voice-a03/audio-libs/root/usr/lib/x86_64-linux-gnu
export LD_LIBRARY_PATH="$audio_prefix:$audio_prefix/pulseaudio"
python3 -m system_qwen35.app.voice_cli --record-authorized --output eval/qwen35/a03/mic-consented-new
```

按提示开始/停止，再核对原始转录，只有准确时输入 YES（否则澄清），最多15秒，不录他人/真实患者；原音频退出删除，转录/诊断默认保存在明确输出目录。人工可懂度表先填 `eval/qwen35/a03/listening_review.csv`；空白不能解释为通过。没有授权时只运行合成WAV流程。

## 已知不足

- 合成12条CER约9.09%，`气短→气断/气弹`、`过敏→过年`等实际错误保留；字面否定/数字未缺失不等于医学槽位识别正确。
- 600/900/1200ms在构造的句中停顿均出现后半句遗漏；不主张真实慢语者端点通过。
- Matcha stderr出现 `Unknown token: shei2`，未静默改字典；已有人听清指定短回复，但广泛发音/术语质量尚未审核。
- 音频取消为逻辑取消+播放flush；不保证声学瞬停，也不保证不可中断原生调用的硬实时上界。
- 录音就绪提示在首块真实PCM之后、首块保留；15秒是采样数限制，异常设备断连/阻塞时严格墙钟上界未测，列入A08可靠性检查。200轮spool和请求额度维护也未验收。
- 版本/资源错误明确失败；依赖冷安装离线包、ARM交叉构建、板端和声学回采均不在当前通过范围。

最新报告：`eval/qwen35/a03/closeout-v1/REPORT.md`，交接：`docs/handoffs/A_A03_CLOSEOUT_20261002.md`。原`REPORT.json`和原交接是录音前历史，原样保留，不用其旧“待授权”覆盖当前结果。llama-cpp技能用于保留A01固定CPU入口/隔离边界，未重建或全局替换模型运行库。
