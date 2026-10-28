# A04 独立参考与优化 CPU 路径

`scalar.py`仅使用Python标准库：直接按行/组构造W字节和Sw，独立A8量化、INT32和、FP32逐次舍入；不import导出器/HLS/C++。`w4a8.cpp`用独立C++行循环实现pack/A8/scalar，并提供32lane连续访问、跨T复用的`tiled`；不借用Python预期。两个实现可共用公共数学/手算fixture，不能互相调用产生预期。性能只报C++，Python不代表S1速度。

## 构建与入口

真实g++11.4构建见`platform/qwen35/a04/build.sh`；A唯一队列执行，产物在`/home/member-a/qwen35-a04/build-v1`。正式数值参考`-O3 -fno-fast-math -ffp-contract=off`、单线程、不用`-march=native`；ASan/UBSan独立`-O1`二进制。vectorization.txt证明整数lane循环实际16byte向量化。此为x86电脑构建，不是ARM或Csim。

```text
w4ref pack N K fp32_input_file new_output_directory
w4ref pack-bf16 N K raw_bf16_file byte_offset new_output_directory
w4ref run N K T w_file sw_file fp32_x_file new_output_directory
w4ref run-q N K T w_file sw_file xq_file sx_file new_output_directory
```

CLI输出JSON统计、返回0成功/2参数或数值拒绝。每次写新目录，不覆盖失败；y/sums/xq/sx保留。头文件可复用，但不是SP_LINEAR_V1动态模块或完整S1运行时；A05再接。调用裸指针scalar/tiled之前必须由调用方完成environment/Shape/validate及缓冲区分配。

## 已验证

- 包内手算`0x97/0x2f`及`890/-891`；相邻行半字节、正负半整数、跨组尺度、全零、subnormal、INT32组上界113792、K129/N33/T1..8。
- 禁止-8/-128、非有限/非正尺度、W/X尾非零、pad行scale非1、短长buffer、uint64极长参数。非零scale下溢0拒绝；FP32恢复溢出拒绝，无输出假PASS。
- FP32固定顺序：`2^24 + 1 - 2^24`得到0，而不是double/重结合的1；恢复必须`(float(sum)*Sw)*Sx`。
- 210断言通过，同套消毒器再运行210；72真实BF16矩阵独立重打包全部匹配；48真实投影与Python独立预期整数/FP32逐位相同。

优化计时包含激活量化、读取原tile，无必要额外完整重排；文件读入/语义校验单列，非每token必须重复。数值检查/诊断sum输出有额外成本。测试每投影一次，无预热分布、p95或产品速度主张；完整运行时内存与稳态性能待A05。原浮点→量化的误差单独报告；无板硬件误差null。
