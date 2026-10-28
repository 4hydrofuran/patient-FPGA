# A07 无板收口：PASS_A07_OFFLINE

2026-10-04，成员A。范围为默认XRT六函数库、已验收B核的真实目标链接/布局布线、Cortex-A53交叉构建和可搬移交付复现。**不是G1板测通过，不是模型已消费PL结果，不是B04联合签核。** BOARD、ARM执行、实际BO预算/带宽、功耗、声学时延均为NOT_TESTED/null。

## 交付与来源

- 正式无板交付目录：`release/a07_b04_v3/`。入口`README.md`、`a_delivery.json`，逐文件SHA256见`files.sha256.json`。v1历史发布及v2打包失败目录保留，不覆盖。
- B04：Git分支`b/qwen35-compute`，commit `9a75600e0df8816f4b9134b5c39d67965310dcd3`，本地`hw/linear_B_received/B04-scope-9a75600-20261003/`；逐项核对Git blob/接收清单，不合并B整仓或修改原件。
- 实际核：B e227297 double，build_id `0xB3030002`，A06已独立接收冻结。XO SHA256 `96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23`。
- 新xclbin SHA256 `bdcb66ca69279e0109928d7b32c3ea0325f617a267e1869636944ba3c193b5fa`；UUID `ec6bb114-e3e0-7c8a-9194-4d75b3275325`。同次构建bit/HWH随包附带，未生成或声称可启动SD/DT组合。
- 公共契约整包哈希为`83bd402b…ee3b6`；其C头文件哈希为`d97e5444…1a76f9`。两者哈希范围不同，契约/头文件字节均未改。

## 分域验收

| 域 | 实际结果与边界 |
|---|---|
| PC共用主机规则 | 干净交付重编译运行970断言PASS；相同ASan/UBSan PASS |
| PC归档meta | 66笔实际历史RTL meta、396篡改、4个错误build检查PASS，相同sanitizer PASS；不是新RTL仿真 |
| PC完整C ABI控制 | 29场景/554检查、相同ASan/UBSan PASS；用醒目标记的XRT传输替身注入故障，不计算假矩阵，不填FPGA_REAL |
| Csim | 当前B源、本地Vitis2026.1实际61例/2800022检查PASS，A04独立参考；与另一任务相同61例不计成122独立案例 |
| Cosim/综合 | 沿用A06已核验同版原报告：65 native PASS+1历史postcheck恢复，66归档输出复核；本轮未重跑RTL。HLS -0.40ns估计不冒充实现值 |
| 实际目标实现 | `v++ --link --target hw`成功，未使用host/hw emulation；原约150MHz约束未降低，源/XO/数学未修改 |
| ARM64构建 | 真实SDK Cortex-A53生产XRT库/独立host编译链接PASS，6个C导出、9依赖；干净包再次构建PASS。旧完整S1/llama/CPU库136单元及ISA/依赖证据按hash复用 |
| 交付预检/复现 | B原始preflight读取真实ARM ELF与全部必需角色，exit0；独立干净目录构建/测试/前后hash核验exit0；这不代替B签核 |
| BOARD/ARM运行/真BO/恢复/A12 | 全部NOT_TESTED，部署profile仍禁用，实际预算null |

重复执行sanitizer或干净复现只是验证方式，不增加不同案例数量。干净重建host字节一致；XRT库哈希不同（二进制可见构建目录相关nlohmann诊断字符串），已逐项记录，不宣称库位级可复现。交付保留已审计生产库与其准确hash，代码输入完全一致。

## 实现报告，不是板端性能

报告来自新生成的routed checkpoint，见交付`reports/implementation/`：

- WNS **+0.809ns**、TNS 0；WHS **+0.010ns**、THS 0；WPWS +1.833ns。三类失败端点均0；12类check_timing检查均0，包括未约束端点、无时钟和组合环。
- 60,541条可布线网络全部完成，routing errors=0。CDC原文“All paths are Safely Timed”，只属静态分析。
- 默认DRC有**93条DSP流水性能警告、18条DSP常量控制建议**，无Critical Warning/Error；不写成DRC零告警。原核功能/Csim已闭环且当前时序满足，进一步流水优化列P2，不改变核或压低严重级别。
- methodology有2条官方平台clock wizard建议（CLKC-40/56），保留原约束与报告。
- 全设计LUT=27,572、FF=40,665、RAMB36=42、RAMB18=5、DSP=100、URAM=0；核层级LUT=14,757、FF=21,027。它们是布局布线资源，不是运行吞吐/功耗。
- HWH的实际核`ap_clk`=149,998,500Hz，routed约束6.667ns。通用core metadata另列KERNEL_CLK=299.997MHz，不将其错当本核实际频率。
- linked XML的17参数、类型/offset/端口/控制协议与冻结XO一致。六个指针参数均逻辑连接HP0/group3，重复的同组GROUP_CONNECTIVITY行明确保留。2GiB是链接地址窗口，**不是可分配BO或Linux内存证明**。

## 实施与所有权

实际代码在`modules/linear_A/xrt/`；重现/控制测试/审计在`platform/qwen35/a07/control/`及`b04/`。六函数异常转错误码、持久device/kernel/run、load时W/Sw唯一BO所有权、预分配I/O池、实际group_id、部分sync、meta先验、Y延迟消费已验证控制流。POISONED下不释放可能仍DMA访问的BO、不接新任务、不卸载、不自动abort/reset或静默CPU回退。驱动state/sync阻塞仍不能承诺硬实时。

逻辑I/O池194656B，72矩阵W/Sw有效数据140378112B，均非实测DDR占用；GGUF页、sidecar页、暂存页到A12另行实测。未启用任何假BOARD_VERIFIED配置。应用目前仍为有效的CPU同数学模式。

## 实际命令与退出码

所有命令的完整argv/cwd/时间/stdout/stderr保存在同目录JSON，非从报告标题推断：

| 收据 | 命令/结果 |
|---|---|
| `control-v2-run.json` | 队列运行`control/build.sh`，PC控制+san+实际SDK ARM编译，exit0 |
| `csim-run.json` | 当前核独立Csim队列，exit0；A06最终报告另保留 |
| `interface-resume.json` | 实际XO/profile/生产参数绑定审计，exit0 |
| `link-run.json` | `v++ --link --target hw --save-temps --platform …/kv260_base.xpfm --config …/link.cfg --vivado.synth.jobs 2 --vivado.impl.jobs 2 --output w4a8.xclbin …/w4a8_linear_v1.xo`，exit0，工具耗时28分13秒 |
| `audit-v3-run.json` | xclbinutil提取实际节、Vivado打开routed DCP生成timing/route/DRC/CDC/methodology/utilization/clocks，exit0 |
| `implementation-review.json` | 逐字段/报告内容核验与SHA生成，exit0 |
| `package-v3-create.json` | 包构建与B原始preflight，exit0 |
| `clean-run.json` | 独立目录`verify_package.sh`，主机/控制/ARM重建与hash，exit0 |
| `closeout-command.json`、`package-final-verification.json` | 最终清单及实际预检/hash收口，均exit0，1101文件 |
| `contracts-final.json`、`config-final.json` | 历史契约保护、新版配置检查，各exit0 |

唯一共享构建队列串行运行、独立work目录，不共用B/C build。不重装工具、不重跑模型/语音/200轮、不改变WSL MAC或重启。

## 失败、设计差距与下一步

保留四类实际失败：PC缺OpenSSL开发头（私有提取匹配dev/runtime后通过）；审计请求不存在的可变时钟节；SYSTEM_METADATA要求RAW导出；v2清单混淆整包/头文件hash。前两次audit及v2包均保留，不删失败样本；只修A工具，不改变B核或公共定义。

最后Windows证据封存工具首次读取中文JSON时受默认GBK影响exit1；改为显式UTF-8重试，首次命令记录保留。该失败发生在已通过的包复现之后，不改变二进制或测试结果。

P0/P1无板缺口已收口：生产C ABI控制覆盖、真实核实现、匹配A53构建、portable交付与复现。P2未实现：额外并行/更深DSP流水、arena/异步预取、固定MAC的独立Linux迁移；不以建议计收益。

后续仍需KV260启动/固件/DT/内核/XRT配套核实、MemTotal/CMA/BO窗口与预算、真实装载执行恢复、A12模型PL结果消费；A09尚有系统/ARM语音等独立未决项。见包内`platform/qwen35/a07/control/PLATFORM_RISKS.md`。Common Image/SDK库匹配不等于KV260可启动，不刷写、不拼未经核实的DT。

本轮不改当前分支/index，不新commit或push；用户现有未提交修改保留。GitHub上原v1部分交付未被冒充为本次完成版。许可证正文/权重/SDK/WSL镜像均不入交付。运行模型设置未更改，无法读取时记unknown。
