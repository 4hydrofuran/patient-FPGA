# B01完成报告｜2026-10-02

B01开发与数值验收已完成，工程门槛PASS，可以进入B02。工程位于 `D:\KV260-project-HLS\b_qwen35`，分支 `b/qwen35-compute`。原B2/B3工程、冻结包、A/C模块均未改动。

## 按任务要求的交付清单

| 任务条款 | 已完成内容 | 证据 |
|---|---|---|
| 1 独立标量参考与手算字节 | 独立dense INT64/FP32参考保持与B00字节相同；新增FP32量化标量参考；0x97/0x2f及[890,-891]硬编码交叉检查 | reference/、tb/golden_w4a8.hpp、hand_sample原始数据 |
| 2 舍入、scale、尾块、保留码、长度、有限数 | 27量化断言、32主机拒绝例、私有核原5类错误、INT32逐位检查、冻结FP32容差 | tests/support/、host/、logs/b01/native_test.log |
| 3 两形状T1..8确定向量 | N3584/K1024和N1024/K3584各T1..8；全部输入/输出/seed/expected及SHA保存；追加真实layer0两权重T1/T8电脑回放 | vectors/b01/、vectors/b01_real/、vectors/model_source/ |
| 4 重复job与错误语义 | 相同/不同job、5次成功累计、1次错误后旧Y不消费/计数不增、恢复合法任务；主机拒绝不启动核 | tb/tb_w4a8_linear_v1.cpp、repeat_jobs向量、native/Csim/RTL postcheck |
| 5 原B2新尺寸覆盖 | 同一保存字节32案例PC回放通过；原B2全部16新尺寸Csim通过；新尺寸Cosim明确NOT_TESTED | baseline/b2/src/、baseline_test及baseline_csim receipts |
| 6 独立入口与开发负载 | run_selftest.ps1不依赖A/C/板卡；JSON负载含seed、shape、布局、字节量、容差、各域状态；ZIP解压重新构建且328文件hash一致 | run_selftest.ps1、docs/b01/workload.json、clean_repro.receipt.json |


## 改动路径与数学边界

- `reference/quantization.hpp`、`reference/README.md`：独立FP32量化；dense expected入口仍为 `tb/golden_w4a8.hpp`，不调用HLS或打包寻址生成期望。
- `host/linear_validation.hpp`：测试用主机校验适配层；长度/指针检查先于内容读取，非法输入不启动核或消费输出。
- `tb/tb_w4a8_linear_v1.cpp`、`tb/compare_b2.cpp`、`tests/numerical/`、`tests/support/`：手算、边界、全新尺寸、重复job、负例和原B2相同输入回放。
- `src/`：只将X/Y仿真深度4864扩大至38912元素，私有build_id更新为0xB3010001；核的数学、冻结FP32顺序、布局、错误语义和ABI不变。
- `run_selftest.ps1`、`run_b01.ps1`、`run_real_reference.ps1`、两份HLS配置：独立执行入口；`docs/b01/`负载及计划；`reports/b01/`与`logs/b01/`证据；`artifact/b01/`新XO及metadata。

固定公共契约SHA256：`83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6`。17个核参数字段与B3核metadata一致，元数据40字节；公共C11/C++17声明检查通过，尚无六符号动态库实现（B04）。旧B2/B3的51个受保护文件SHA保持原样。

独立参考每组INT64精确累加，恢复顺序为FP32(FP32(sum*Sw)*Sx)，按group升序FP32相加。每组合法整数和上界113792，INT32逐位比较。旧例绝对容差1e-6；新形状固定atol=1e-4、rtol=1e-5，没有因结果放宽。

## 分域结果与实际退出码

| 执行域 | 实际结果 | 退出码 / 覆盖 |
|---|---|---|
| PC一键selftest | PASS | 0；C11/C++17、27量化检查、32主机拒绝例、43合成核事务、B2同字节32案例、4真实权重回放 |
| 当前核PC | PASS | 0；2,140,479个INT32部分和、173,728个FP32输出检查；全部16新组合 |
| 当前核Vitis Csim | PASS | 0；完整full套件43事务，全部16新组合 |
| 原B2 Vitis Csim | PASS | 0；完整full套件43事务，全部16新组合；原B2源码未改 |
| 新综合与XO | PASS | 0；Vitis 2026.1，xck26，目标周期6.667ns；新核XO而非旧产物 |
| Vitis原生Cosim总流程 | FAIL，保留 | 1；生成C编译/链接阶段失败，首次未进入RTL验证 |
| 当前核实际RTL恢复执行 | PASS_RECOVERED | XSIM=0，cosim.pc.exe输出校验=0；25事务，含两种新形状T1及小边界/错误/重复job |
| 原B2新形状Cosim | NOT_TESTED | 未执行，不由旧尺寸历史报告推断 |
| 当前新形状T2..8 RTL、真实权重Csim/RTL | NOT_TESTED | T8完整RTL覆盖在B03；真实权重扩展本轮仅PC |
| 干净ZIP解压重建 | PASS | 0；35个必要源/输入文件提取校验，328个重新生成向量文件hash全部一致 |
| 平台链接、实现、ARM64、BOARD、问诊质量/端到端速度/功耗 | NOT_TESTED | 无板阶段，无对应测量 |

全部合成新尺寸和4个真实权重回放案例的max_abs=0、NRMSE=0（以本机此次测试为限）。RTL postcheck实际输出检查为5664个；其日志中58175个整数检查来自独立helper/reference回归，并不代表RTL内部部分和被逐项探针采集。

综合估计资源：BRAM_18K=117、DSP=58、FF=17068、LUT=30801、URAM=0。估计周期5.241ns，时钟不确定度1.80ns；相对6.667ns目标的估计预算余量约-0.374ns，因此不宣称完成150MHz时序收敛。动态顶层延时报告未知，未用估计计算板端tokens/s。

## 一键入口、命令和证据

在工程根目录运行：

```powershell
.\run_selftest.ps1
```

这是B01全部电脑数值自测入口，使用包内真实权重，不下载、不需要Vitis/板卡。其退出码0。分项命令也实际执行并保留退出码：

```powershell
.\run_b01.ps1 -Target reference        # compile/test均0
.\run_b01.ps1 -Target native           # compile/test均0
.\run_b01.ps1 -Target baseline         # compile/test均0；先native
.\run_b01.ps1 -Target csim             # 0
.\run_b01.ps1 -Target baseline_csim    # 0
.\run_b01.ps1 -Target synth            # 0
.\run_b01.ps1 -Target cosim            # 首次1，保留；恢复步骤见RTL_RECOVERY
.\run_real_reference.ps1              # compile/test均0
```

依赖为MinGW GCC/G++（本机 `D:\mingw64\bin`），Vitis步骤另需本机2026.1与许可证。兼容环境仅对进程生效，不改工具安装或全局设置。源码ZIP提取后重复运行相同入口；该重建限PC，不声称重新综合。

`reports/b01/*.receipt.json` 保存真实工具参数、退出码及输入SHA；`logs/b01/` 保存测试输出；`numerical_metrics.csv` 逐例误差；`docs/b01/workload.json` 为开发负载清单；每份向量manifest保存原始字节SHA。

向量seed规则 `0x20261002 + shape_index*256 + T`，shape_index=0为gate/up，1为down。W为[N_tile32][K_group128][k][lane_pair16]，偶数lane低nibble；X为[T,Kp]、Y为[T,Np]。两种目标W均1,835,008字节，Sw均114,688字节；其它字节量按各T逐项记录，不是实际总线流量。

## 真实权重来源与验证限度

官方 `Qwen/Qwen3.5-0.8B` 固定revision `2fc06364715b967f1860aea9cf38778875588b17`，layer0 `gate_proj.weight` [3584,1024]与 `down_proj.weight` [1024,3584]，各完整BF16矩阵7,340,032字节。HTTP Range核对Content-Range/长度，原始张量SHA和转换后FP32 SHA记录在 `vectors/model_source/source_manifest.json`；附官方config/index/header/LICENSE。完整1.75GB模型未下载，整文件SHA明确为null。

BF16仅以bit左移16扩展FP32；每份权重各T1/T8，合计4电脑案例。真实权重检查516,096个INT32部分和、41,472个FP32输出，max_abs与NRMSE均0。激活是固定seed合成输入；本轮不代表全部矩阵、真实层激活、模型logit或问诊质量通过。

## 失败保留、未决项与下一步

首次当前Csim出现本机MSYS进程错误，原日志/收据已保存在 `evidence/b01/initial_tool_attempt/`，同源码顺序重试通过。原生Cosim生成C阶段失败；诊断关闭多线程/移除CPATH后生成object完成，但内置链接仍报错。使用本机MinGW与低image base重新链接后，实际XSIM与Vitis RTL输出回放通过。各次失败收据保留，恢复流程见 `docs/b01/RTL_RECOVERY.md`。

B01数值门槛没有剩余阻塞。进入B02前应复现记录的本机RTL恢复流程；原生工具总流程仍未恢复为0。B02需在当前正确核上测计算和AXI瓶颈，分别记录tile缓存/激活复用的构建标签并跑同一冻结回归，验证综合时序预算。B03补两目标T1/T8完整RTL；B04实现公共动态库和平台链接。

客户端Sol/High/Standard实际设置仍未经核实；板卡/平台profile未知。本包为B01开发与数值证据包，不是可部署问诊系统或B04调用库候选。
