# 成员B：Qwen3.5计算后端

B01已完成，工程数值门槛PASS；先读PROJECT_STATUS.json、docs/b01/TEST_PLAN.md和docs/b01/workload.json。
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
