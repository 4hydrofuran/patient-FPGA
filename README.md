# KV260 离线标准化病人协作工程

当前阶段：A0，无板契约与平台准备。当前没有 FPGA 推理实现，没有上板通过证据。

原工程已由用户放在 `originalpatienqwen/`，保持只读；执行包在 `KV260Paper/KV260_三人协作执行包_20260926/`。
这些目录及旧交付文件被新仓库忽略，不上传 8B 权重、历史语音或凭据。

## 先读这些文件

- `AGENTS.md`：角色边界及操作限制。
- `docs/status/A.md`：A 的实际状态与下一步。
- `docs/handoffs/A0.md`：命令、证据及交接入口。
- `contracts/README.md`：四份机器/人可读契约、共同样例、评审流程。
- `docs/handoffs/A0_to_B.md`、`docs/handoffs/A0_to_C.md`：B/C 的独立开发入口。
- `platform/BOARD_PLAN.md`：无板计划、租约及到板验收。

## 本机自检

Python 3.10+，以下检查仅使用标准库，不安装项目依赖。

```powershell
python scripts/release/check_contracts.py
python -m unittest discover -s bench/runtime/tests -v
python scripts/release/run_common_sample.py --cxx D:/AMDDesignTools/2026.1/tps/mingw/10.0.0/win64.o/nt/bin/g++.exe
```

共同 C++ 样例是主机端字节/布局互认，不是 HLS Csim/cosim。B 仍须独立编写 golden 和核。
API 文件为合法 JSON 形式的 YAML，避免额外解析器依赖；运行时服务尚未实现。

## 协作状态

只有 A 本机仓库，尚无 remote；未创建 B/C 工作区。获得成员地址后由各成员独立 clone。
契约状态为 DRAFT，不能把本机测试通过理解为三方冻结。冻结须绑定内容 SHA256 和三方评审。
用户通知板卡 10 月 7 日以后到；原 9 月 30 日板测关口不可达，原后续排期必须重新评估。
