# 2026-10-02 C 成果整理与 Git 发布记录

用户要求先检查原工程、整理已完成工作，再推送到 `4hydrofuran/patient-FPGA`。原 `C:/vivado/KV260` 不是 Git 仓库；已有远端默认分支为 `b/qwen35-compute`，检查时 HEAD 为 `cdb3e4634116b79e4673354dc21ccc6eabed1e32`。

本次在独立克隆目录整理，新增分支 `c/voice-c00-c04-20261002`，继承上述提交和全部 B 历史。B 源码、公共契约、冻结测试与证据保持原提交内容；仓库根 README 只增加 C 导航，Git 忽略规则和文本属性补充 C 发布路径。没有在原工程中初始化 Git、迁移目录或重写旧阶段证据。

## 整理后的目录

| 路径 | 内容 |
|---|---|
| `patient-qwen/` | 旧应用源码及 UI 资源；凭据已移至环境变量，历史音频与平台二进制排除 |
| `workspaces/C/app/`、`cases/`、`quality/`、`bench/` | 历史 C0/C1 应用、合成病例、冻结问答、指标、待审核表和工程证据 |
| `workspaces/C/voice_C/` | C00—C04 worker/client、ASR/TTS/流式/麦克风模块、录音计划、盲听空表、锁定来源和阶段记录 |
| `workspaces/C/docs/` | 当前任务指导、阶段交接、状态与迁移差异 |
| `workspaces/C/releases/c04/` | 单一最终 ZIP 与 SHA256；不重复上传试跑包、构建副本或带模型的运行环境 |
| `docs/publication_c_20261002/` | 原目录清单、逐文件导出 hash、排除记录、上传前验证与复核入口 |

最终 ZIP 为 67,616,313 字节，SHA256：`f507c5d1792a6477a38ce29f60fff76b3cfe98e00e2ef2830574c87d20547006`。它保留原离线 Windows/ARM wheel、源码快照和 Git bundle；独立源码目录只保留 dependency lock，不重复这些依赖二进制。

## 导出与排除依据

`export_manifest.json` 逐文件记录原 SHA256 和发布副本 SHA256。只有旧工程的凭据脚本和 `.env.example` 做脱敏修改；其他导入文件逐字节复制。新增发布说明和导航不冒充原历史文件，也不写入原阶段 manifest。

`exclusions.json` 记录排除路径与原因，主要为虚拟环境、依赖安装目录、IDE/类型检查/Python 缓存、私人麦克风手动测试及采集细节、旧运行音频、模型资源、合成试听 WAV、重复归档和构建副本。两个原始根 ZIP 未上传，其中可能有未经脱敏的旧内容。公开 FLEURS-r 音频保留原署名和 CC BY 4.0 说明；它是开发样本，不是正式真人录音。

已发现旧代码和环境示例中的实际凭据，发布副本不保留其值。检查记录只报告匹配计数，不记录凭据正文；没有调用云服务或验证凭据有效性，也没有代替持有人执行轮换。路径筛选和已知凭据检查不能证明检测到了所有潜在敏感信息。

## 验证口径

原阶段结果：C04 为 103 项回归、30 次新 worker 冷启动和 200 次模块循环通过；最终 ZIP 的独立安装、49 项自测和真实 ASR/流式/TTS 烟测通过。这些原始记录保留在 `workspaces/C/voice_C/evidence`。

发布副本另做原文件完整性比对、导出 hash 校验、ZIP 条目/已知凭据检查、49 项无需模型的工程检查以及旧 C0/C1 各 27 项检查。此次不重新生成模型测量、不打开麦克风、不覆盖历史证据。具体命令、结果和退出码见 `validation.json`。

封存文档里的 `published=false` 和 `NOT_SENT` 是历史状态，保持原内容；本次 Git 推送不代表 A 已接收、默认系统已替换、真人质量/模型许可通过或已经上板。Git 远端提交结果由实际 push 和远端 commit hash 复核，不在 push 之前声称上传成功。

复核导入文件：在仓库根运行 `python docs/publication_c_20261002/verify_export.py`。它不写任何历史文件。原 manifest 中提到的被排除资源仍留在原本地工作目录，因此不要把原阶段 manifest 当成完整 Git checkout 的文件清单。
