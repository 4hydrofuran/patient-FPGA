# reference_B：独立标量数值参考

`quantization.hpp` 提供 `reference_b::quantize_weights`、`quantize_inputs` 和显式 ties-to-even 的 `round_code`。输入为有效行主序 FP32 数组；权重按每行每 128 个有效 K 值取 absmax/7，激活按每条有效输入行取 absmax/127，全零 scale=1。非有限输入、非正或不可表示的 scale 明确拒绝。

`../tb/golden_w4a8.hpp` 的 `golden_dense` 是独立 expected 入口，输入为未打包 W4、行主序 Sw、零 padding 的 A8 和逐 token Sx。它不包含 HLS 头文件、不调用待测核、地址或解包函数，也不通过 packed 权重生成 expected。每组用 INT64 精确累加并输出 INT32 部分和；每项恢复为 FP32(FP32(sum*Sw)*Sx)，按 group 升序累加。

合法输入每组最大绝对整数和为 128×7×127=113792，落在 INT32 范围内。整数部分和要求逐位一致；新目标形状逐元素固定 `abs(error) <= 1e-4 + 1e-5*abs(expected)`，旧边界保持原有 1e-6 绝对容差。所有编译入口禁止 FP contraction。NRMSE 定义为 sqrt(sum(error²)/sum(expected²))；参考能量为零时以零误差为通过条件。

固定手算交叉检查：W=[[7,-1],[-7,2]]、X=[127,-1]、Sw=Sx=1，packed 首字节 0x97、第 16 字节 0x2f，Y=[890,-891]。这些字节和输出是硬编码检查值，未由核生成。

执行 `../run_selftest.ps1` 可完成 C11/C++17 头检查、独立量化 27 项检查、全部合成形状、同字节 B2 回放，以及两份固定真实权重的电脑回放。单独量化检查执行 `../run_b01.ps1 -Target reference`，完全不链接 HLS 源码。

公共六符号调用库仍归 B04。`../host/linear_validation.hpp` 是 B01 测试适配层；后期调用库应复用冻结契约和本测试数据，不能把它视为已有 XRT 驱动实现。
