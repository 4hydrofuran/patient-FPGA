# B03 设计与消融边界

## 固定条件

X[T,K]×W[N,K]^T→Y[T,N]；T1..8；K按128补齐，N按32补齐；每group INT32、(FP32(sum)*Sw)*Sx，group递增FP32累加。公共契约不变，内部顶层参数及40字节meta布局不变。构建ID：baseline=0xB3020002、reuse=0xB3030001、double=0xB3030002。

## 调度

T1继续执行B02_X128的token→output tile→group路径。新增T>1路径先缓存有效T条A8行和每条Sx，随后按output tile→group→token处理。一个2048字节W4 tile和32个Sw服务全部token；只保存当前输出tile的8×32个FP32累计值，输出仍为[T,Np]。并不代表处理8个不同会话，也不包含注意力、SiLU、完整模型调度。

Sw master明确固定为32位。初始优化版让HLS自动拓宽到512位，综合报告显示decode的原突发读取因数据宽度不同而退化，gate/up T1实测558,926周期，比基线530,254慢5.41%。该尝试原样保留，修正后必须重新综合和实际RTL验收；不能以C++保留相同T1分支推断硬件周期不变。

reuse：装载一个group，按token依次计算，再装载下一group。

double：每个output tile先装载group0；偶数group计算first槽并装载second槽，奇数group反向。prefill_overlap中的装载/计算任务并行，函数返回前两个任务均完成，外层才能交换所有权。最后group has_next=false，没有越界预取。当前tile全部group完成后顺序写Y，不声称store也与下一tile装载重叠。

W4保留码仍在全部计算之前完整预扫，非法输入不产生部分Y。输入A8/scale与padding主机检查由已有测试适配层负责；B04六函数库和超时DMA生命周期不属于本阶段实现。

## 请求字节口径

两种目标尺寸的每个矩阵均有W4=1,835,008字节、Sw=114,688字节。baseline的W4预扫加计算共(T+1)遍权重，reuse/double共2遍（预扫+一次计算装载）；T8逻辑W4读取由16,515,072降到3,670,016字节，减少77.78%。scale由T遍减到1遍。T1逻辑读取不变。

以上只为源码算法请求，不能当作AXI/DDR物理实测。实际乘加仍需执行T份，速度不按请求比例推算。

## 验证与限制

PC/Csim full为50次事务、两种目标尺寸各T1..8与量化/错误/重复/尾块。nominal RTL为34次事务，包含两种目标尺寸T1/T8；周期按TRANSACTION标签映射。stress为32次事务，包含全部小边界与新增最大K4864/T8和最大N4864/T8，采用工具cosim.random_stall与明确的cosim.user_stall JSON，五个内存master各地址/数据/响应通道随机延迟0..7周期、control为0..3周期，事务延迟保持64。默认只随机化control的历史组不计入最终内存背压验收。INT32 partial检查观察C++ MAC helper；RTL内部部分和没有独立调试输出，RTL结果验收基于Y/meta回放。

HLS资源、II和slack均是估计；XSIM周期未含板端DDR争用、量化和同步。公共共享库、xclbin和实现后时序归B04；BOARD和整机指标保持NOT_TESTED。候选只从已通过全部要求的构建中选择，decode和prefill分别列数值，不用平均值掩盖回退。
