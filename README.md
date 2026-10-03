# 成员B：Qwen3.5计算后端

当前为 **B03无板验收完成（2026-10-03）**：baseline、reuse、double各34笔普通RTL通过；唯一候选double另通过32笔随机背压RTL。两种目标T1与基线周期相同，T8收益与资源代价见[验收报告](docs/b03/B03_REPORT.md)及reports/b03/ablation.json。Sw保持32位，消除自动拓宽造成的decode退化。[三方案阶段快照](docs/b03/THREE_SCHEMES_STATUS.md)保留历史暂停状态。B04公共动态库、实现时序和板测尚未完成。

B02 无板访存消融已完成，选 `B02_X128` 作为 B03 开发基线：在每 token A8 缓存上将激活 AXI 口从 512 bit 限为 128 bit。它使 HLS 估计 BRAM_18K 从 CACHE_X 的 120 降到 78，两种目标 T=1 尺寸分别只多 1 个 XSIM 周期；相对 B01，gate/up 快约 1.29%，down 慢约 0.25%。X128 原生 Cosim 25/25 通过，但实现时序和板测未做。运行 `.\run_b02_x128.ps1 -Target native|csim|synth|cosim` 复现新候选；旧 `B02_CACHE_X` 及冻结 B01 配置继续保留。完整选型、消融、证据和限制见 `docs/b02/SELECTION_AND_DELIVERY.md`，当前分域状态以 `PROJECT_STATUS.json` 为准。

B01已完成，工程数值门槛PASS；B01 复现仍读 docs/b01/TEST_PLAN.md 和 docs/b01/workload.json。
核沿用B3的32-lane数学与ABI，只扩X/Y仿真窗口到38912元素并将私有构建ID更新为0xB3010001。

在本目录执行 `.\run_selftest.ps1` 可一键完成全部电脑数值自测（含包内真实权重，不下载、不需要Vitis或板卡）。分项入口：
- .\run_b01.ps1 -Target native：新形状T1..8与历史边界、主机负例、重复job；生成vectors/b01。
- .\run_b01.ps1 -Target reference：不链接HLS的独立量化检查。
- .\run_b01.ps1 -Target baseline：原B2消费完全相同的保存字节（先native）。
- .\run_b01.ps1 -Target csim 或 baseline_csim：当前与原B2全形状Vitis Csim。
- .\run_b01.ps1 -Target synth，之后cosim：当前综合/XO和代表性新形状T1 RTL回归；平台链接未做。
- .\run_real_reference.ps1：固定官方版本layer0 gate/down权重的T1/T8电脑回放，激活为合成。

依赖：MinGW GCC/G++（默认D:\mingw64\bin）、Vitis 2026.1（工具步骤），匹配许可证和原有本机兼容环境。
无A运行时、病例或C语音依赖。真实权重源见vectors/model_source/source_manifest.json；需要重新取得时运行tools/download_model_tensors.py。
六符号SP_LINEAR动态库尚未实现；host/linear_validation.hpp为B01数值校验适配层；本包不是B04部署候选。
全部原始数据与expected在vectors/b01和b01_real；报告/日志在reports/b01、logs/b01；核产物在artifact/b01。
B00冻结包继续保留，根B00_PACKAGE_MANIFEST为历史快照；不要用它核验当前B01文件。旧run_b00/run_b3为历史入口，阶段复现使用B00冻结包。

本机Vitis原生Cosim总流程曾失败；实际RTL通过来自保留生成物后的链接恢复与输出回放，见docs/b01/RTL_RECOVERY.md。不能把首次退出码1改写为0。
