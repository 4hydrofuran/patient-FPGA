# B3 首轮接口依据

用户于 2026-10-01 明确确认：A/B 冻结接口与当前 B2 一致。本记录保存本轮采用的边界，不替代 A 项目中可能另存的契约文件。

- B2 源码 SHA-256：`F0B4FE682AD350E98DCFC47272E7A83262AD978A053AF64467968B8DCBE6DAC2`。
- B2 头文件 SHA-256：`0E382ABD938FCDA7CF259308E9D3EBEBF24B37EA3BEE4FCD4C9AEB00FE1DB413`。
- 顶层仍为 `w4a8_linear_v1`；参数顺序、固定宽度类型、五个 master bundle、`ap_ctrl_hs` 和 AXI4-Lite 控制沿用 B2。
- `abi_version=1`，`KernelMeta` 保持 40 字节；状态码 0～5 与错误时输出不变的规则不变。
- B3 构建标识为 `0xB3000001`，用于区分新数据通路；A 应接受此构建值，而非误要求所有版本都返回 B2 标识。
- 量化组为 K128，输出 tile 为 N32。每组按 INT32 点积，再以 `(float(sum)*sw)*sx` 恢复，按 group 顺序 FP32 累加。未开启 unsafe math。
- W4 补码低半字节对应偶数 lane，高半字节对应奇数 lane；有效码为 -7..7，-8 拒绝。有效 N/K 以外的 padding 不参与保留码判错。
- `Kp=ceil(K/128)*128`，`Np=ceil(N/32)*32`，`G=Kp/128`。最小字节容量依次为 `w:Np*Kp/2`、`sw:Np*G*4`、`x:T*Kp`、`sx:T*4`、`y:T*Np*4`、`meta:40`。
- T=1 是本轮性能目标；原 T=1..8、N/K=1..4864 的功能边界保留。没有新增跨 token 权重复用或并行队列。
- 输入/输出/meta BO 不重叠，调用期间保持有效。meta 首次调用前清零。元数据无法写入时依旧直接结束而无法报告错误。

本轮只修改核内部结构、构建标识和为测试扩大 `m_axi depth`；平台端口到 memory group 的连接仍由 A 最终链接验证。
