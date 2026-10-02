# B2 → A 交付说明（2026-09-29 验证版）

## 一句话结论

这是可供 A 做主机侧接入和接口评审的 **B2 首版正确性核**：当前源码已通过 Vitis HLS 2026.1 C 仿真、C 综合、XSIM C/RTL 联合仿真，并成功导出 `.xo`。它还不是上板可用的 `xclbin`，也不是 B3 的高吞吐优化版；A/B 尚需冻结正式 ABI。

## 版本与可核查证据

| 项目 | 当前结果 | 证据文件（交付包内） |
| --- | --- | --- |
| 目标 | KV260 器件 `xck26-sfvc784-2LV-c`；时钟目标 6.667 ns（约 150 MHz） | `hls_config.cfg` |
| Vitis 版本 | 2026.1，HLS Build 6493734 | `reports/csynth.rpt` |
| C 仿真 | PASS，手算、双 scale/K 尾部、N 尾部、保留码边界、重复调用及错误路径 | `reports/csim.log` |
| C 综合 | 估算周期 5.241 ns（估算约 190.81 MHz）；BRAM18K 68、DSP 26、FF 15730、LUT 29066 | `reports/csynth.rpt` |
| C/RTL 联合仿真 | XSIM Verilog PASS，9/9 个顶层事务；延时 251～15743 周期（平均 3589） | `reports/cosim.rpt`、`reports/transactions.rpt`、`reports/hls_run_cosim.log` |
| IP/XO 打包 | `w4a8_linear_v1.xo` 成功生成；XO 内嵌 C++ 源码哈希与交付源码一致 | `artifact/w4a8_linear_v1.xo`、`reports/hls_run_package.log`、`manifest.json` |

这些数值是 HLS 综合和测试样例的结果，不能当作布局布线后的实际 Fmax、完整模型推理时延或板端性能。旧版 `B2_STATUS.md` 中的 8.036 ns、6 个事务属于优化前基线，不对应本包。

## A 接入时必须遵守的当前接口

- 顶层函数 `w4a8_linear_v1`，控制为 `ap_ctrl_hs` 和 AXI4-Lite；参数及类型以 `src/w4a8_linear_v1.hpp` 和 `artifact/kernel.xml` 为准。请用 XRT kernel metadata 的 `group_id` 分配缓冲，不要手写 AXI 地址偏移。
- 这是 **预量化输入核**：A/主机负责生成 `w_packed`、`sw`、`xq`、`sx`。核不接受文本或 FP32 原始权重，也不在 PL 内做 absmax/量化。
- `T=1..8`，`N,K=1..4864`；`Kp=ceil(K/128)×128`，`Np=ceil(N/32)×32`，`G=Kp/128`。缓冲最小长度：`w_packed=Np×Kp/2` 字节，`sw=Np×G×4`，`xq=T×Kp`，`sx=T×4`，`y=T×Np×4`，`meta=40`。
- W4 是 32 输出 lane × 128 输入元素的分组打包；同一字节低半字节为偶数 lane，高半字节为奇数 lane。合法 W4 为 `-7..7`，`-8` 是拒绝码。具体偏移公式和手算例见 `golden/` 与 `B0_INTERFACE_DRAFT.md`。
- 每 128 元素先得到 INT32 点积，逐组按 `(float(sum) * sw) * sx` 恢复后累加为 FP32 输出；`y` 的 N 尾部填充 lane 写 `0.0f`。
- `abi_version=1`。`KernelMeta` 为 40 字节，含 `abi_magic=0x57344138`、`kernel_build_id=0xB2000001`、原样返回的 `job_id`、`status`、`done`、完成计数和算法权重字节数。首次调用前，主机须将 `meta` 缓冲清零，否则累计计数的初值不确定。成功时 `status=0, done=1`，完成计数加一；错误调用时通常 `done=1`、计数不加、`y` 不改写。唯一例外：`meta` 为空或短于 40 字节时无法回报错误，函数直接返回。
- `status` 值：0 成功、1 ABI 错、2 维度错、3 缓冲过短、4 空指针、5 W4 保留码。错误时不要消费旧 `y`。

## 交付边界与 A/B 待确认

1. 本包的 `KernelMeta`、五组 AXI 主端口 bundle、最大尺寸、错误语义仍是 B2 可执行草案；B0 的 Q01～Q07 尚未由 A/B 签字冻结，`kernel_v1.yaml` 尚未形成。若 A 需要修改 ABI，必须让 B 更新源码并重跑 Csim、综合、Cosim 与 `.xo` 打包。
2. `artifact/w4a8_linear_v1.xo` 是 B2 接入候选。A 仍需在实际 KV260 平台上进行 `v++ --link`/生成 `xclbin`、主机 BO 分配与调用、板端正确性及实现后时序检查；本包不声称这些已完成。
3. 测试覆盖的是手算及小尺寸边界/错误事务；尚无完整模型权重、真实 MLP 形状回归或模型问诊验证。B3 的 32-lane 并行、宽 burst/tile cache 和目标吞吐也未完成。
4. 如果要重现本机导出，参见包根目录的 `hls_package.cfg`、`run_hls.ps1` 和 `run_cosim.ps1`。脚本里 `D:\2026.1`、`D:\mingw64` 是本机工具路径，移机时需要按实际安装位置调整。英文临时 Vivado 用户数据目录仅为规避本机中文用户路径下的打包报错，不属于核 ABI。

## 建议 A 的验收顺序

先用 `golden/` 的手算向量核对 A 侧打包和 BO 长度，再检查 `.xo`/`kernel.xml` 的参数与 `group_id`，随后选择平台链接并运行主机端。若接口项需要调整，先回传 A/B 共同确定的字段和布局，不要在主机端悄悄兼容另一种解释。

## 在同版本 Vitis 上复现

从解压后的包根目录运行下列步骤；C 综合使用同一个 `build/cosim` 工作目录，联合仿真才可复用它的 RTL。首次执行可能需要先按本机情况修正 Vitis 路径和 PowerShell 脚本中的环境设置。

```powershell
& 'D:\2026.1\2026.1\Vitis\bin\vitis-run.bat' --mode hls --csim --config hls_config.cfg --work_dir build\cosim
& 'D:\2026.1\2026.1\Vitis\bin\vitis-run.bat' --mode hls --config hls_config.cfg --work_dir build\cosim
.\run_cosim.ps1
& 'D:\2026.1\2026.1\Vitis\bin\vitis-run.bat' --mode hls --package --config hls_package.cfg --work_dir build\cosim
```

本包内的报告和 `.xo` 已由原工作区运行取得；上述命令是复现路径，不表示在交付目录另行跑过一遍。可以先用 `manifest.json` 的 SHA-256 核对收到的源码与 `.xo`。
