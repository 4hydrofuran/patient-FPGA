# 成员 B：Qwen3.5 计算后端

当前 B00 工程验收通过。唯一工作分支 b/qwen35-compute；基础为已验证 B3 32-lane。
本包不是 B04 可部署候选，公共调用库尚未实现，新模型形状/真实张量未执行；历史 XO 仅保存在冻结备份内。

首次阅读 PROJECT_STATUS.json、docs/b00/B00_CHECKLIST.md、docs/b00/INTERFACE_AUDIT.md。
电脑自测：在本目录执行 `powershell -NoProfile -ExecutionPolicy Bypass -File .un_b00.ps1`。
依赖为本机 MinGW GCC/G++（默认 D:\mingw64\bin，可传 -MingwRoot）。不需要 A/C 工程或 Vitis。
run_b3.ps1 是继承的工具入口；baseline 使用本包 baseline/b2/src，不依赖相邻旧工程。
如执行后续Vitis任务，需匹配安装与许可证；报告和产物须更新版本绑定。

src/tb 为继承源码/独立参考；tests 为新增B00检查；contracts/fixtures 为原样公共规格和固定样例。
docs/plan_qwen35 为任务包参考副本；其测试声明不作为本模块验收。
evidence/history 为冻结历史证据；reports/logs 为本轮记录；build/vectors/generated 为本地生成缓存。
后续按 B01 开始验证 N3584/K1024、N1024/K3584、T1..8；具体种子、负例与门槛见 docs/b00/test_plan.json。
