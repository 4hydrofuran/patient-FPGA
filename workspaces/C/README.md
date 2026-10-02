# 成员 C：历史应用评测与离线语音成果

这是 2026-10-02 从原工作目录整理出的 Git 发布副本。旧 C0/C1 和新版 C00—C04 分开保留；它们不是同一套任务编号。原工作目录与封存证据保持原内容。本次公开范围和排除项见 [发布说明](../../docs/publication_c_20261002/README.md)。

| 阶段 | 实现与验证 | 尚未完成 |
|---|---|---|
| 旧 C0 | 三个合成病例、会话隔离、受控披露、规则评分；27 项检查 | 医学教师审核、真实主应用接入 |
| 旧 C1 | 冻结 324 条测试问答、54 条开发记录、独立评测器和两位教师待填表；27 项检查 | 真实模型评测、教师标注和临床质量 |
| C00 | SP_VOICE_V1 JSONL worker/client、取消与重置、路径约束、48 条录音计划；35 项检查 | 自有正式录音、转录核对、授权记录 |
| C01 | 固定中文 INT8 ASR；14 个公开开发片段、126 次运行；阶段 49 项检查 | 真人最终 CER、ONNX 导出权重外发许可 |
| C02 | Matcha Baker + Vocos 中文 TTS；正式 138 次合成；阶段 67 项检查；14 条待填盲听表 | 真人发音/自然度试听、相关许可核对 |
| C03 | 200 ms PCM 流式输入、partial 展示、finish 唯一 final、端点提示；阶段 89 项检查 | 主应用接入与真人流式质量 |
| C03 麦克风 | Windows WinMM 输入及驱动夹具；实际 10 秒/50 块采集传输通过；两环境各 99 项检查 | 当次没有朗读，不能认定识别质量通过；后续私人记录不发布 |
| C04 | 103 项回归、30 次新 worker 冷启动、200 次语音模块循环；最终包独立安装及 49 项自测通过；真实 ASR/流式/TTS 烟测通过 | 物理断网 OS 重启、实际出声、完整应用端到端、ARM 原生运行及板测 |

上述计数按各阶段分别记录，不能相加成为当前唯一测试总数。C01 开发 CER 为 148/606 ≈ 24.42%，这是公开修复语音的小型开发切片，不是学生、医学术语或最终真人验收成绩。C04 的 200 轮是模块循环，不能称为完整患者系统端到端测试。

## 从哪里看起

- 最新交接：[docs/handoffs/C04.md](docs/handoffs/C04.md)、[voice_C/C04_README.md](voice_C/C04_README.md)。
- 源码：`voice_C/voicec`；协议入口：`voice_C/bin/worker.py`；麦克风说明：[voice_C/MICROPHONE_README.md](voice_C/MICROPHONE_README.md)。
- 历史应用：`app`、`cases`、`quality/c1`；记录：[C0](docs/handoffs/C0.md)、[C1](docs/handoffs/C1.md)。
- 当前指导：`docs/plan_qwen35`；旧任务不能按编号重新宣称新版通过。
- 最终工程包：[releases/c04/C_pc_candidate_v1.zip](releases/c04/C_pc_candidate_v1.zip)，含离线依赖 wheel、源码快照 Git bundle、公开烟测及署名；不含模型资源或私人音频。

## 快速运行 49 项无需模型的检查

以下命令从仓库根目录执行，需要本机 Python 3.12。创建的 runtime 和结果目录必须不存在；自测不会打开麦克风。最终 ZIP 是固定交付物，不能直接在解压包中写运行结果。

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python docs/publication_c_20261002/verify_export.py
Expand-Archive -LiteralPath workspaces/C/releases/c04/C_pc_candidate_v1.zip -DestinationPath .local_c_candidate
python .local_c_candidate/tools/verify_bundle.py .local_c_candidate --contract .local_c_candidate/contracts/contract_lock.json
python .local_c_candidate/tools/install_candidate.py --target-runtime .local_c_runtime
& ./.local_c_runtime/.venv/Scripts/python.exe ./.local_c_runtime/bin/selftest.py --output .local_c_results
```

上述安装只使用最终包中的固定 Windows wheel。独立发布源码目录不重复保存这些 wheel。模型尚缺失，真实自测需另外取得有权使用的固定资源、逐文件核对 `model.lock.json`，再按包内说明运行 `--real`。单独运行 Git 源码的全部 103 项检查也需要模型与依赖；缺少资源时应失败，不应跳过后宣称 103 项通过。ARM wheel 只有静态准备证据，不能据此认定 A53 可运行。

旧 C0/C1 的检查需要 `app/requirements-c0.lock.txt` 中的依赖。可在独立虚拟环境安装，然后从 `workspaces/C` 执行：

```powershell
python -m unittest discover -s app/tests -v
python -m unittest discover -s quality/c1/tests -v
```

请勿运行历史 `finalize_*`、`verify_c00.py`、`run_c01_checks.py` 或重建冻结材料的脚本覆盖阶段证据。新的模型回归用 `VOICE_C_TEST_EVIDENCE_DIR` 指向新的证据目录。

## 历史记录与许可

C03 首次回归曾覆盖两份 C02 自测探针，原内容没有被伪造还原；事件记录保留，正式 138 次合成测量未受影响。C04 首次独立自测因 stderr marker 冲突失败，修复后通过；失败记录也保留。

封存交接中的 `NOT_PUBLISHED` / `NOT_SENT` 等描述是当时的历史状态；本次 Git 发布不修改它们，也不等于 A 已接收或默认系统已采用。尚未填入的人工评分保持 null/PENDING。ASR、Baker、Vocos 导出资源许可仍待确认，Baker 数据存在非商业限制；来源和 hash 的公开不代表获得权重分发许可。公开 FLEURS-r 开发音频保留 CC BY 4.0 来源、署名与变换说明。没有为来源未知的旧工程素材补造开源许可。
