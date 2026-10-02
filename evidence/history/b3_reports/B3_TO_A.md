# B3 首轮接入要点

本轮候选核位于 `artifact/w4a8_linear_v1.xo`，metadata 位于 `artifact/kernel.xml`。核名仍是 `w4a8_linear_v1`。源码、构建配置、测试和实际验证结论见包根目录 README 与 `reports/B3_STATUS.md`。

候选核已通过本机 Csim、综合和 XSIM C/RTL 联合仿真，RTL 共 19 次调用，含完整合成 up/down。尚未平台链接、板测或真实模型测试；专项源码可读性门限仍有未通过项。

## 与 B2 的兼容边界

生成的 17 个参数的 name/type/size/offset/port/addressQualifier 已逐项与 B2 metadata 核对一致。五个 AXI master 宽度保持 W128、Sw32、X512、Y32、Meta512，控制口为 32 bit。原有 BO 长度计算、W4 打包布局、KernelMeta 40 字节结构和 status 值保持不变。

唯一需要主机识别的构建变化是 `kernel_build_id=0xB3000001`。请勿将冻结的 `abi_version=1` 与可随构建更新的 build_id 混为一项。A 的平台 memory group、最终链接与实际时序尚未在本轮验证。

## 第一组接入输入

建议先使用 `vectors/generated/hand_sample.*`：T=1、N=2、K=2、Np=32、Kp=128，预期前两项 Y 为 890 和 -891，其余 padding 输出为零。对应最小 BO 字节容量如下：

| BO | 字节容量 |
| --- | ---: |
| w_packed | 2048 |
| sw | 128 |
| xq | 128 |
| sx | 4 |
| y | 128 |
| meta | 40 |

后续使用 `mlp_up_synthetic.*` 和 `mlp_down_synthetic.*`。每个 case JSON 记录实际维度、padding、seed 和数据来源；所有二进制文件使用小端，scale/输出为 FP32，partial 为 INT32。输入 byte hash 位于 `vectors/generated/manifest.json`。这些是合成向量，不是医学训练数据或模型真实张量。

## 主机侧核对

根据 kernel metadata 为各参数选择 memory group，不硬编码寄存器偏移或假定不同 bundle 就对应独立 DDR 带宽。首次调用前清零 meta，调用前同步输入，完成后同步输出与 meta。必须同时检查预期的 job_id、build_id、status=0、done=1 及完成计数增长，再使用 Y。

本轮未提供 A 平台的 connectivity 配置或 xclbin，需由 A 在实际平台链接候选 XO。B 配合回放数据不一致，任何错误都应保留输入字节、输出、XO/xclbin hash 和调用日志。
