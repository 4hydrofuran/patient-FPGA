# A07 → B04：共享XRT运行时交付

此入口构建 A 维护的六函数库及独立主机程序，B 维护核。公共头与 W4A8 数学不变。

## 可复现构建

交付根中的 `third_party/nlohmann/json.hpp` 来自已锁定 llama.cpp 源码，其 MIT 许可声明保留在头部。工具依赖：Linux g++、Python3、匹配的 AMD 2026.1 Common AArch64 SDK（XRT 2.23、uuid、OpenSSL、libstdc++开发依赖）。不分发工具、SDK或许可证。

在新空目录执行（参数都由接收者提供，不依赖 A 盘符）：

```bash
bash /absolute/delivery/platform/qwen35/a07/b04/build_portable.sh \
 /absolute/delivery /absolute/delivery/third_party/nlohmann \
 /absolute/sdk/environment-setup-cortexa72-cortexa53-amd-linux
```

编译 PC 主机规则、ASan/UBSan、B 的66筆实际归档meta回放；然后生成 `libsp_linear_xrt_candidate.so`、`sp-linear-host`。明确 `-mcpu=cortex-a53 -O3 -fno-fast-math -ffp-contract=off`，不使用native/i8mm/dotprod。XRT当前API废弃警告保留，不自动换装载路线。ARM ELF只交叉构建，不在PC执行。

## 运行边界

config中的文件路径相对于config所在目录，非调用者cwd。`config.pending.json` 不允许设备访问；它需要的KERNEL_SOURCE随包提供，accepted/frozen仍为false。没有完整物理profile不得手填BOARD_VERIFIED。

独立host的 `--check-unavailable CONFIG` 只测试open明确不可用；`--execute-hand CONFIG` 是未来实际板端手算入口，涉及实际load_xclbin，必须前置验收及到板授权。本阶段未执行它。手算W=[[1,-1],[2,-2]]、X=[3,1]、尺度1，输出[2,4]及30个0；期望不是核自产。

成功load复制并持有W/Sw，原数组可释放。X/Sx/Y在run期间有效。输出只有SP_OK可消费。失败/超时POISONED保留资源，独立host不会在未知DMA状态下自动退出/卸载；它明确等待运维恢复，不是自动恢复功能。不得kill后宣称安全。

## 单一所有权

| 对象 | 唯一所有者/寿命 |
|---|---|
| 原sidecar映射、CPU量化输入 | 模型层；load完成后可解除目标层临时页 |
| W/Sw BO | XRT上下文的weight handle，load→安全unload |
| X/Sx/Y/meta BO、device/kernel/run | XRT上下文，open→安全close；steady-state复用 |
| POISONED所有权 | registry保留；未经设备静止证明不释放、不换位流 |
| 原GGUF其他层与状态 | 模型层；A12才证明完整模型实际消费PL结果 |

本包没有整模型权重，实际BO预算、CMA、group/address window均null。常驻BO不能再重复计成另一份CPU模型。

## 验收分账

PC规则与归档meta回放不是BO/PL执行；ARM编译不是ARM运行；旧vadd链接不是本核链接。`a_delivery.json`标PARTIAL时，B完整preflight必须拒绝缺件，不能把`missing_roles`的文字当实际xclbin。G1～G6联合签核由各方明确完成，不由脚本自动代签。

平台候选kv260_base 2026.1_0608_1339、器件xck26-sfvc784-2LV-c，默认约150MHz；B HLS slack=-0.40ns仍是风险。完整v++、路由报告/DRC/CDC缺失即G4未通过。Common rootfs/SDK库一致也不等于KV260启动链、DT、XRT匹配已通过。
