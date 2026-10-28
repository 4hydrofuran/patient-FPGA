# B03 三方案阶段交付与恢复入口（2026-10-03）

**历史阶段快照：基线完成后暂停开发时的交付。** 本文对应Git提交fdd1d65，不代表恢复开发后的实时状态；当前状态见PROJECT_STATUS.json。2026-10-03用户恢复优化验收后，Sw端口已修正为固定32位，原512位尝试独立保存在evidence/b03/sw512_regression/。以下保留原阶段说明。

恢复后的最终结果见[B03验收报告](B03_REPORT.md)：三版各34笔普通RTL与唯一double候选的32笔内存随机背压均已通过，B04实现与板测仍未完成。

当时baseline实际RTL 34/34通过；reuse和double已完成代码、PC、Csim和综合，但完整RTL未完成。B03尚未最终验收，唯一交付候选尚未选定。不要把这份历史Git快照当作B04可部署候选。

## 1. 三个方案的原理和区别

三个方案计算同一个`X[T,K] × W[N,K]^T → Y[T,N]`，保持32路整数乘加、同一FP32恢复和沿group递增的累加顺序。T1是decode路径；T>1是prefill路径。同一批输入共享权重，并不包含多会话调度或完整问诊模型。

| 方案 | 数据搬运与计算安排 | 代价与预期收益 | 源码及主要配置 |
|---|---|---|---|
| baseline / B02_X128 | 每个token分别遍历权重；输入行缓存，X AXI为128位 | 已验证的比较基线；T8仍重复读取权重 | `baseline/b02/src/w4a8_linear_v1.cpp`；`hls_prefill_baseline.cfg` |
| reuse / 权重复用 | T>1缓存全部输入；按输出tile→group→token处理，一块W4/Sw服务全部token | 减少重复读权重，增加输入和累计缓存；加载与计算顺序执行 | `src/w4a8_prefill_v1.cpp`；`hls_prefill_reuse.cfg`；`B03_REUSE` |
| double / 受控双缓冲 | reuse基础上使用两个独占W4/Sw槽；计算当前块时装载下一块，两项任务均结束后交换 | 可隐藏部分搬运等待，增加缓冲和控制资源；实际收益尚待RTL消融 | 同一优化源码；`hls_prefill_double.cfg`；`B03_REUSE + B03_DOUBLE_BUFFER` |

reuse减少搬运次数；double在相同搬运次数上尝试重叠加载与计算。double不声称输出写回也与下一tile重叠：当前输出tile全部group完成后才写Y。最后group关闭预取，非法W4完整预扫结束前不写任何Y。T1保留原decode计算路径，但新增硬件的实际周期影响仍需两版RTL分别验证，不能先宣称无回退。

两种目标形状均有W4 1,835,008字节、Sw 114,688字节。T8含预扫描的逻辑W4请求从baseline的9遍（16,515,072字节）降到reuse/double的2遍（3,670,016字节），减少77.78%；Sw从8遍降到1遍。计算仍有8份；上述数值不是AXI/DDR物理实测，也不是已验证的速度提升。

## 2. 当前验证状态

| 验证域 | baseline | reuse | double |
|---|---|---|---|
| PC合成数值 | PASS，50笔 | PASS，50笔 | PASS，50笔 |
| 真实权重PC | PASS，4例 | PASS，4例 | PASS，4例 |
| 完整Csim | PASS，50笔 | PASS，50笔 | PASS，50笔 |
| 综合/XO生成 | PASS | PASS | PASS |
| 普通RTL | **PASS，34/34笔** | 未完成，早期中断不计PASS | 未完成，早期中断不计PASS |
| 随机背压RTL | 未运行 | 未运行 | 未运行 |
| 实现/aarch64/BOARD/质量/整机时延/功耗 | NOT_TESTED | NOT_TESTED | NOT_TESTED |

PC/Csim包含两个目标形状`(N,K)=(3584,1024)/(1024,3584)`各T1..8、历史形状、量化/主机/核错误、重复job及新增N65/K257尾块。真实权重为固定revision `2fc06364715b967f1860aea9cf38778875588b17` 的layer0 gate/down两份权重，T1/T8共4例，激活为合成输入，不代表全模型或问诊质量。紧凑日志和收据见`evidence/b03/verification/<variant>/`；真实权重来源/许可见`evidence/b03/model_source/`。

INT32部分和核对观察C++ MAC helper；RTL验收核对实际Y/meta，并未独立探测RTL内部部分和。独立dense golden不调用待测核生成expected；历史1e-6与目标形状`1e-4 + 1e-5*abs(reference)`门槛保持不变。

### 基线真实RTL周期

| 目标形状 | T | 总周期 | 每token周期 |
|---|---:|---:|---:|
| gate/up：N3584、K1024 | 1 | 530,254 | 530,254 |
| gate/up：N3584、K1024 | 8 | 2,601,183 | 325,147.875 |
| down：N1024、K3584 | 1 | 524,414 | 524,414 |
| down：N1024、K3584 | 8 | 2,555,583 | 319,447.875 |

来源：`reports/b03/baseline_acceptance.json`与`evidence/b03/batches/baseline/<group>/manifest.json`。这是本轮隔离suite的XSIM周期，后续优化版须使用同一suite比较；不要混用B02历史多事务周期，也不要换算成已达到的板端服务速度。

普通RTL分为smoke30笔，以及gate_t1/gate_t8/down_t1/down_t8各1笔。已核验(case,T,N,K)多重集合与原34笔套件完全一致。每组单独启动和退出，普通组关闭波形，避免多个高内存仿真进程并行。

其中down_t1原生流程PASS；smoke/gate_t1/gate_t8经本次object重链接、真实XSIM及POST_CHECK恢复通过；down_t8原生RTL完整结束后POST_CHECK启动失败，明确重建回放程序后实际输出核对通过，标`PASS_POSTCHECK_RECOVERED`。原生退出1、原始失败日志均保留；未观测的down_t8 RTL子进程退出码为null，不能编造为0。详见`RTL_RECOVERY.md`。

额外反证：明确POST_CHECK程序接受正确归档RTL数据；只在临时副本把手算Y[0]从890改成0时明确报错，原始归档SHA不变。见`reports/b03/postcheck_consumer_proof.json`。

### HLS资源与时序估计

| 构建 | BRAM18K | DSP | FF | LUT | slack(ns) |
|---|---:|---:|---:|---:|---:|
| baseline | 78 | 58 | 15,105 | 28,006 | -0.37 |
| reuse | 132 | 90 | 22,082 | 37,177 | -0.40 |
| double | 137 | 104 | 24,351 | 39,289 | -0.40 |

目标时钟6.667ns、器件xck26-sfvc784-2LV-c；double综合报告检测到prefill_overlap的两个DATAFLOW任务。资源/slack是HLS估计，负slack不证明实现后达到150MHz。源到综合的指纹、XO CRC和参数/控制偏移检查通过，见`reports/b03/artifact_guard.json`。

公共契约SHA256：`83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6`。私有meta仍40字节；ID分别为baseline `0xB3020002`、reuse `0xB3030001`、double `0xB3030002`。内部scale AXI端口由baseline 32位扩为优化版512位；公共布局和顶层参数/控制偏移不变，后续集成使用对应kernel.xml。

## 3. 仓库内容和本机原始数据

Git提交包括三方案源代码/配置、冻结B02、独立golden与测试、验证入口、状态/设计/失败和恢复说明、成功日志/收据以及每组性能文件与SHA清单。未冻结任何最终候选。

大体积tv数据、波形、完整构建目录和模型权重不进入Git。本机原始基线证据仍在`D:/KV260-project-HLS/b_qwen35/evidence/b03/batches/baseline/`；manifest列出完整原始文件的SHA。重生成合成输入使用固定seed。新克隆执行真实权重回放前，需从原任务交付数据恢复`vectors/model_source/`，或按既有`tools/download_model_tensors.py`取得固定版本两份张量；来源和许可已经随紧凑证据上传。

本机运行环境为Vitis/Vivado 2026.1、D:/mingw64/bin及D:/codex-vitis-shims兼容辅助程序。脚本仅调整进程环境；没有安装软件、修改全局配置或上板。辅助程序和工具安装不随Git提交，移机需先按上述恢复说明提供相同依赖。

## 4. 恢复开发时的顺序

本轮已暂停，没有继续运行的B03仿真。恢复时先核对`PROJECT_STATUS.json`、公共契约和当前源指纹，保留本次基线成功证据。

1. 对reuse和double分别刷新PC/Csim，再逐组完成smoke/gate_t1/gate_t8/down_t1/down_t8。使用已存在的分组入口，成功归档后才允许下一组覆盖构建目录。
2. 生成独立消融表，比较两种目标形状各T1/T8周期、每token周期和HLS资源，单列decode回退情况。缺少优化版完整RTL时不得填性能提升。
3. 根据实测选择一个候选。应力testbench已准备stress_basic/lifecycle/tail/max_k/max_n五组（12/11/7/1/1笔，总32）及静态配置；本机PC分组检查已通过，RTL尚未运行。**目前runner的Target stall仍运行合并32笔，需要先接入上述分组选择再进行受控背压验收。**
4. 完成所选候选随机背压RTL、原始输出回放和覆盖一致性检查，才冻结唯一B03候选并做最终交付。
5. B04再实现公共六函数库、BO驻留/同步/超时poisoned安全生命周期、目标平台xclbin离线链接、实现时序/资源与aarch64构建。BOARD仍需单独验收。

已有普通分组命令：

```powershell
.\run_prefill.ps1 -Variant reuse -Target native
.\run_prefill.ps1 -Variant reuse -Target csim
.\run_prefill.ps1 -Variant reuse -Target cosim -Group smoke
python tools/archive_prefill_batches.py --archive reuse smoke
# 同样依次执行gate_t1/gate_t8/down_t1/down_t8；随后对double重复
# 三版全部34笔完成后才运行汇总：
python tools/archive_prefill_batches.py
```

禁止把进度条或仅链接成功当作功能PASS。整个阶段最终状态只有在优化版与背压必需项完成后才能改为COMPLETE_OFF_BOARD。
