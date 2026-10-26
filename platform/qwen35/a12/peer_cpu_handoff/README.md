# 给队友：A12 CPU任务01部分＋任务03

日期：2026-10-24（北京时间）。本包是**无板开发基线**，不包含已完成的优化候选。维护者A；接手方在独立候选中开发并署名，不修改本包原件。

你要完成两件事：①把节点计时按实际操作和权重身份正确分类；②保持逐token矩阵计算的原有数值方式，减少之后的反复拼接、复制和节点同步。完整PL核不是本任务的依赖；本包不加载XRT、不连接板卡。

## 从哪里开始

1. 完整解压到一个新目录，先阅读 `TASKS.md`、`BASELINE.json`、`ACCEPTANCE.md`。
2. 在Windows Python或Linux/WSL执行：

   ```text
   python3 -B tools/verify_package.py
   ```

3. 在Linux/WSL执行下列命令。建议先把ZIP解压到WSL本地文件系统（例如自己home的新目录），避免在 `/mnt/c` 上逐个访问1700余份源码造成明显I/O等待。工作目录必须是包目录外、尚不存在的新目录；已有CMake、C/C++编译器、OpenMP即可，不下载依赖、不需要模型、板卡或XRT：

   ```text
   python3 -B tools/build_and_test.py --work /tmp/a12-peer-baseline-01 --jobs 2
   ```

4. 如需覆盖更多实际维度，用另一个新工作目录：

   ```text
   python3 -B tools/build_and_test.py --work /tmp/a12-peer-full-shapes-01 --jobs 2 --full-shapes
   ```

默认运行108个合成投影组件用例：F32/Q4_K/Q6_K权重、T0—8、连续/非连续行、1/2线程；额外选项增加18个真实维度族的合成用例。这些比较当前稳定hook与同ISA逐token原语，不是独立量化golden，不是完整模型回归。计时观察器测试是6项**旧基线行为刻画**，其中明确保留“未命名矩阵乘落入默认桶”的已知缺口；PASS不表示任务01已修复。

5. 复制本包到独立候选目录，修改候选源码和测试，并以 `TASKS.md` 的新验收要求开发。原包 `verify_package.py` 检查的是冻结基线；候选不能改旧manifest后冒称原包一致。候选自己生成manifest、记录补丁和基底哈希。

`tools/build_and_test.py` 是旧基线自检入口。候选新分类需要新增目标行为测试；不能删掉旧基线缺陷刻画记录，也不能继续用其旧断言证明分类修复。

## 包内内容

| 路径 | 内容及身份 |
|---|---|
| `source/llama/` | 必要固定运行时源码：src/include/cmake/ggml/vendor及许可；A05补丁已在其中 |
| `source/llama/ggml/src/ggml-cpu/ggml-cpu.c` | A12轻量观察器版本，核对过任务10派生SHA |
| `source/runtime/sp-hook.*` | 实际A12稳定投影hook，任务03主入口 |
| `source/profile/request_profile.*` | 实际A12节点分类与汇总，任务01主入口 |
| `context/` | 主模型图、A12 main/bridge/route、原构建说明等阅读材料；无本包启动入口 |
| `contracts/qwen35/` | 公共数学/ABI字节副本，保持原hash |
| `baseline/` | 小型实测指标、版本及原始聚合剖面；不能恢复未采集的逐节点耗时 |
| `history/` | A05失败/修复材料、冻结输入、相关回归源码；只读参考 |
| `tests/`、`tools/` | 本次新增的可移植组件自检与包校验 |
| `fixtures/PROFILE_CASES.json` | 交给接手方实现的新分类目标用例，不冒充已通过 |
| `templates/` | 交付结果模板，所有未测结论保持null/NOT_TESTED |
| `PROVENANCE.json`、`MANIFEST.json` | 每份原文件来源/哈希、复制/派生关系、包内全部文件清单 |
| `validation/`（如有） | 出包方实际执行的组件验证摘要，具体范围见其JSON |

没有模型权重、sidecar payload、PL位流/XO、SDK、WSL镜像、构建二进制、账号、密码、密钥、令牌或商业许可证。运行时MIT及其依赖许可保留在源码内；模型许可证副本是公开许可，不是工具授权文件。

## 基线版本与移植约束

- 模型：Qwen/Qwen3.5-0.8B，文本、非思考；模型revision见 `BASELINE.json`。
- 运行时基准commit：`81e39ad34368329b5db77620721510fd91107e80`，已叠加A05图/加载器/稳定注意力策略和A12观察器，不等于未修改上游。
- 当前稳定hook及图、CPU ops、公共头、观察器的SHA见 `BASELINE.json`。不要使用你电脑上同名旧文件代替。
- 组件CMake只编译ggml与两个合成测试，不构建模型服务。原llama `src/CMakeLists.txt` 中A侧绝对路径保持原字节作为历史来源；若未来构建完整llama，必须在独立派生副本参数化hook路径并记录机械补丁，不能套用本机原路径。
- PC测试使用本机ISA；PC时间不能换算成A53速度。ARM交叉构建如做，使用现有2026.1 SDK、`-mcpu=cortex-a53`、`GGML_NATIVE=OFF`，单列CROSS_BUILD；不能用开发机 `-march=native` 交叉构建。
- 不启用fast-math、FMA重结合或普通批量GEMM来掩盖复制开销。不重新导出权重、不改变归约顺序。
- 源码中上游自动生成的git版本文字不是基线证明；以固定commit、补丁及manifest为准。

## 无板可以证明与不能证明的内容

可以证明：包完整性、分类目标与父子/融合计时规则、PC合成输入的布局/边界/同ISA数值、候选与原基线组件差异、PC内存和PC时间；具备对应环境时可做ARM交叉构建。

不能证明：真实模型24层logits和状态正确、PL输出真实消费、板端TTFT收益、实际CPU/PL加速比、XRT完成/取消/释放、CMA与温度门禁、正常卸载恢复。BOARD保持NOT_TESTED，硬件周期/功耗/板端速度填null。

完整模型与实板接入由A接收后执行；本包不要求你从其他工程拼凑权重或自行下载替代模型。如果你本地已有匹配模型，先核对 `assets/MODEL_ASSETS.json`；完整模型PC回归是额外证据，不能以本包合成测试替代，也不能声称本包已提供完整服务部署环境。

`history/reference_scripts/` 是原工程的历史回归源码，含原工程相对路径与依赖，仅供理解用例和移植，不是本包的独立执行入口。所有可直接运行的入口均在上面的 `tools/` 命令中。

## 回交

按 `DELIVERY.md` 提交独立压缩包，不发整仓、不改原B工程、不推送远程、不包含凭据和模型权重。保留失败及无法确认项。A负责集成、同板新旧对照与最终验收；两人工作范围不得同时覆盖管理许可链、公共契约或PL核。
