# B04：B 侧阶段交付

本包是 `B04_B_STAGE_PARTIAL`，用于 A07 接入 B03 double 核。用户已采用 A07/B04 分工边界，并确认 A 尚未交付。本包完成 B 侧核适配资料、独立检查和阶段包复现准备；完整 B04 仍等待 A 运行时、目标实现及联合验收。

候选 build_id 为 `0xB3030002`，私有 meta 为 40 字节。`config/b04/kernel_profile.json` 来自实际 XO/XML 和真实核头编译结果；`docs/b04/KERNEL_ADAPTER.md` 说明参数、容量、同步和错误语义。公共契约、HLS 源码和 XO 保持 B03 冻结摘要。

## 可在普通电脑复现的内容

需要 Python 3.9+、可运行的 C++17 编译器。Windows 示例使用本机已有的 MinGW；其他电脑请将编译器路径替换为实际路径，无需安装 Vitis 来运行这些 CPU 检查。

```text
python tools/b04_profile.py --cxx D:/mingw64/bin/g++.exe --work build/b04/profile_new --receipt reports/b04/profile_new.json
python tools/b04_selftest.py --cxx D:/mingw64/bin/g++.exe --work build/b04/selftest_new --receipt reports/b04/selftest_new.json
python tests/b04/packaging_checks.py reports/b04/packaging_checks_new.json
```

每次使用新的 `--work` 目录；工具拒绝覆盖旧运行目录，以保留失败记录。profile 检查 17 个参数、实际端口、共享 X/Sx、40 字节布局和冻结摘要。selftest 检查 40 项独立规则，回放 66 笔原始 RTL 完成记录，并拒绝 108 个 job/计数被篡改的记录。原始 RTL 的 meta 和相关标量数据已包含在本阶段包中。

`vectors/b04_meta/manifest.json` 为 A 提供易读的66笔接入样例：每笔包含尺寸、任务编号、调用前计数、实际 meta 长度及 before/actual/expected 二进制文件。expected 原样取自 B03 独立 golden，实际字节取自原 RTL，并非 B04 检查器生成。`completion_bytes_to_inspect` 为实际可检查长度；短 meta 用例即使文件保存40字节，也必须按请求长度截取并拒绝消费 Y。

## 阶段包验证与新目录自测

从独立下载说明取得 ZIP 的 SHA256；包内 manifest 不能独自证明下载来源。下面的工具先检查外部 ZIP 摘要、CRC、成员路径、完整清单和逐文件摘要，再解压、重编译和执行自测。

```text
python tools/b04_stage.py verify B04_B_stage_20261003.zip --sha256 <下载说明中的摘要>
python tools/b04_stage.py extract-test B04_B_stage_20261003.zip --sha256 <同一摘要> --target <尚不存在的新目录> --cxx D:/mingw64/bin/g++.exe
```

新目录检查还会将冻结 double 源码编译到 PC，运行公共固定手算样例的三笔调用：正确输出、有效权重中的保留码拒绝、短输入拒绝。失败时 Y 和成功计数保持原值。此检查直接使用核函数，并不代表公共六函数动态库已实现。

完整数值向量、原始 RTL Y 数据及独立 dense golden 回放在 [B03 补交 Release](https://github.com/4hydrofuran/patient-FPGA/releases/tag/b03-a06-supplement-20261003) 中。ZIP SHA256 为 `506f079daabf37f6dc539d35c49add0b4c0e7629a0a97c461c470b0f75c59513`。本阶段包包含 meta 子集，保持全量数值证据的独立下载引用，不依赖原开发者的 build 目录。

## 等待 A 的交付

见 `docs/b04/A_DELIVERY.md`。A 负责公共调用库、XRT BO/同步、权重驻留、超时与安全关闭、目标 xclbin/实现报告、匹配 ARM64 库及 host。B 负责核资料、独立证据、接入复核和候选组装。

`tools/b04_a_preflight.py` 可检查 A 将来提供的文件身份、摘要、实际 ELF 和六个导出函数；通过仅表示可进入联调审查，不能代签 G1～G6。未收到 A 产物时应保留 `WAITING_A`，不得创建占位 .so/xclbin 或将阶段包改名为完整 `B_pc_candidate_v1.zip`。

新 RTL 仿真未运行（核保持冻结）；XRT 运行时、实际布局布线、ARM64 运行时和 BOARD 均未验收。HLS slack −0.40 ns 是历史估计，真实时序以目标实现报告为准。
