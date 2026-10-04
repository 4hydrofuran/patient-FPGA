# A01—A09 分阶段工程增量包

这是成员A在 **2026-10-04当前工程状态** 的分阶段源码、配置、测试工具和材料快照，不是每个阶段当时的历史checkout，也不是实板验收成品。

已上传基线：[`a/a07-complete-20261004`](https://github.com/4hydrofuran/patient-FPGA/tree/6dd1a93c2fa44b045276c24f4cc79d94e54b88b3)，commit `6dd1a93c2fa44b045276c24f4cc79d94e54b88b3`。该分支的A07完整交付仍在`release/a07_b04_v3/`，本次不重复传其二进制大包；A07压缩包是额外源码/配置/材料补充。

## 分别下载

| 阶段 | 本次工程文件数 | 包 | 内容 |
|---|---:|---|---|
| A01 | 3708 | [A01-engineering-delta.zip](A01/A01-engineering-delta.zip) | 模型锁、结构映射、配置/tokenizer/模板与许可、固定llama源码、基线工具 |
| A02 | 110 | [A02-engineering-delta.zip](A02/A02-engineering-delta.zip) | 合成病例、AnswerPlan/事实检查/规则评分、开发与隔离清单、教师审核模板 |
| A03 | 111 | [A03-engineering-delta.zip](A03/A03-engineering-delta.zip) | 默认语音worker/音频适配器、协议测试、资源锁及音频测试工具 |
| A04 | 89 | [A04-engineering-delta.zip](A04/A04-engineering-delta.zip) | 原权重量化导出器、Python/C++独立参考、边界测试、sidecar manifest |
| A05 | 203 | [A05-engineering-delta.zip](A05/A05-engineering-delta.zip) | 同数学CPU库、图接入/原生入口、状态/批次/数值测试与构建工具 |
| A06 | 78 | [A06-engineering-delta.zip](A06/A06-engineering-delta.zip) | A的核接收/独立复核工具、KERNEL_SOURCE和验收报告；不冒充B核作者 |
| A07 | 53 | [A07-engineering-delta.zip](A07/A07-engineering-delta.zip) | 相对已上传完整A07的补充工程；已有49份同字节文件列为远端引用 |
| A08 | 74 | [A08-engineering-delta.zip](A08/A08-engineering-delta.zip) | 默认整机服务、trace/资源/线程/回归工具及收口报告 |
| A09 | 87 | [A09-engineering-delta.zip](A09/A09-engineering-delta.zip) | 发布/部署/恢复/只读采集/BO探针/目标依赖准备、清单和论文空结果模板 |

九个zip合计22,415,681字节（约22.4 MB）。共享配置/契约会在不同阶段重叠，文件数不能相加当作唯一源码数。每个包的逐文件SHA256及已上传文件所在路径见对应`MANIFEST.json`；zip整体SHA256见[INDEX.json](INDEX.json)。均已逐成员读取、CRC及SHA256核验，不是只检查文件名。

## 如何使用

1. 在**全新工作目录**读取上述固定A07基线，不要覆盖任何成员现有工程。
2. 下载所需阶段zip，解压后`project/`下保留原仓库相对路径。完整工程需结合各阶段，阶段包不保证单独构成可启动应用。
3. 每个manifest的`already_uploaded`是本次未重复上传的同字节内容。用`commit`与`remote_paths`取回文件，再放到该条目的原路径并核对SHA256；不要把远端打包内部路径误当原工程路径。
4. 共享文件应具有相同hash；不自动合并冲突。遵循包内`AGENTS.md`、状态/锁文件和阶段报告。
5. 原构建记录有开发机绝对路径，应按README/构建入口核对当前环境后迁移；不要直接执行会下载资源、录音或创建既有输出目录的历史阶段脚本。此次只发布工程，不重新宣称已在另一台电脑或板上复现。

## 有意不上传

- 模型/语音权重、GGUF、生产sidecar二进制；保留revision、许可、hash和导出/获取入口。
- 原始麦克风录音、音频spool、逐轮私有会话记录、凭据、AMD节点许可证、系统盘/SD/WSL镜像、SDK及工具安装目录。
- 离线wheel安装缓存、完整原始性能日志/波形/大型生成产物。A09完整150MB离线候选仍在成员A本地，不作为本次Git工程zip重复上传。
- B/C整个工程不合并。B核精确来源和已验收文件由A06清单/既有远端引用追踪；C缺候选不影响默认A源码发布。

自动范围排除见[EXCLUDED.json](EXCLUDED.json)。模型卡/tokenizer等是允许保留的公开模型元数据，不包含神经网络权重。语音模型非商业限制仍然适用，未自动公开权重。

## 验收边界

这些包的完整性通过不改变阶段结果：A07离线通过；A09电脑无板演练通过但DEPLOYMENT_PENDING_BOARD。全部BOARD仍NOT_TESTED，教师审核、最终隔离质量、实际声学/功耗、ARM运行和Linux/PL内存预算各自待验。不把HLS估计或PC数据写成板测。

本次发布新A分支，不改B/C分支，不覆盖main，不切换成员A当前工作树，不提交其余脏修改。
