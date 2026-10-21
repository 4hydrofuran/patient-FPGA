# B04 完整电脑候选

本候选组合 A07 公共运行时与 B03 double 核。当前执行状态见 `docs/b04/B04_JOINT_REPORT_20261021.md`、`PROJECT_STATUS.json` 和随包提供的独立解压验收收据。正式候选文件名为 `B_pc_candidate_v1.zip`；试包不使用此名称。文件名本身不代表验收通过。

## 组成与来源

- `src/`、`artifact/b03_candidate/`：B 冻结源码、私有头、实际 XO 与元数据。
- `contracts/`：冻结公共六函数 C ABI、数学及布局。
- `evidence/b04/a07_received_20261021/`：固定 A 提交 `6dd1a93c2fa44b045276c24f4cc79d94e54b88b3` 的原始 `release/a07_b04_v3/`，1,102 个文件逐字节保留。其 `artifacts/` 含实际 xclbin、ARM64 `.so`/host、bit/HWH；其 `modules/linear_A/xrt/`、`platform/qwen35/a07/` 含公共源码及构建入口。
- `tools/b04_joint_pc.py`、`tools/b04_joint_audit.py`、`tools/b04_candidate.py`：B 独立重建、产物审阅与整包验收入口。
- `vectors/b04_meta/`、`fixtures/`：独立期望数据；`reports/b04/joint_20261021/`、`evidence/b04/joint_20261021/`：本轮新收据、原日志与失败记录。
- 根 `manifest.json`：每个文件的大小、摘要、来源与域。完整 B03 原始大向量/波形另按旧阶段包的固定 SHA256 取得；本候选自带无板入口所需的元数据、标量与手算向量，不依赖隐藏开发目录。

核保持 `w4a8_linear_v1` / double / build_id `0xB3030002` / 私有 meta40，XO SHA256 `96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23`。公共契约整包摘要 `83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6`，公共头文件摘要 `d97e544444b8566a32d0bd25e67e2e548f71678ac6e63ac63e96aa415b1a76f9`；两者范围不同。

## 独立解压与自测

需要 Python 3.9+、已有 C++17 编译器、已有 AArch64 readelf 和 xclbinutil。Windows 控制测试另需已有的真实 OpenSSL 3 DLL；不自动安装或更改全局环境。每次使用不存在的新目录。当前 MinGW 的 A C++ 文件系统控制测试要求**完整解压路径为英文/ASCII**，例如 `D:/B04_acceptance`；中文路径试测的编码错误保留为已知限制。B 独立探针已通过中文目录测试；此限制不用于推断 Linux 生产运行时的路径能力。

```text
python -B tools/b04_candidate.py extract-test B_pc_candidate_v1.zip --target <全新目录> --sha256 <外部交付的ZIP摘要> --receipt <本次解压收据.json> --cxx <现有g++> --crypto <Windows现有OpenSSL3-DLL> --readelf <现有readelf> --xclbinutil <现有xclbinutil>
```

该入口先核验外部 ZIP 摘要、CRC、路径、全清单和逐文件摘要，再在解压目录重新编译 B profile/probe、A 主机规则/实际公共后端控制测试和 B 固定核手算样例，并重新读取实际 xclbin 与 ELF。构建后再次检查所有包内输入未变化。

Windows 的 `tests/b04/native/` 只供 `SP_LINEAR_CONTROL_TEST` 使用：摘要调用真实 OpenSSL DLL；文件锁由 Windows 操作系统提供。这验证 Windows 控制流程，不能替代 Linux 的 O_NOFOLLOW/O_CLOEXEC/flock 语义。A 原 Linux 测试及 ASan/UBSan 原命令另按摘要核验。A 源码与传输替身不修改，生产 ARM64 包不含这些适配头或控制替身。

PC 控制测试输出 `execution_kind=null` 且禁止进入公共性能统计；固定零传输哨兵不是数学正确性证据。B 的手算 golden 与冻结核在 PC 单独执行，历史 RTL 结论按原范围复用。本轮不产生新的 RTL/布局布线或板端吞吐数据。

## ARM64 与实现复用边界

本包复用 A 的实际 Cortex-A53 / AMD 2026.1 Common SDK 构建产物及依赖摘要。B 重新检查真实 ELF、六个公共导出、动态依赖、无测试替身和原始编译命令。本机没有匹配的 Linux Common SDK，本轮不冒充新目标构建；原生 Vitis AArch64 工具用于读取实际产物。

在具备匹配 Linux SDK 的机器重建生产库及 host，按 A 原 `README.md` 执行 `platform/qwen35/a07/b04/build_portable.sh`；Linux 控制测试入口为 `platform/qwen35/a07/control/build_control_portable.sh`。SDK、系统镜像、许可证、权重及外部运行库不随包分发，版本/摘要和获取条件在 A 原交付中说明。A 的独立重建库因构建路径诊断字符串不同而不保证位级一致，原产物及两个摘要均保留，不声称 bit reproducible。

## 部署状态

**BOARD、ARM 实际执行、真实 BO/CMA/带宽、故障恢复、时延与功耗均为 NOT_TESTED。** 所有真实部署配置继续禁用；HP0 的逻辑 2GiB 地址窗口不是可分配内存预算。约150MHz实现时序和资源来自 A 的 routed 报告，B 复核原始内容及实际匹配产物，不重跑布局布线。

`README_B04_STAGE.md`、2026-10-03 阶段报告和旧暂停记录是保留的历史阶段说明，不代表本候选最新状态。后续进入 B05 时另以匹配平台和实际板测证据验收。本轮不启用定时任务或邮件。
