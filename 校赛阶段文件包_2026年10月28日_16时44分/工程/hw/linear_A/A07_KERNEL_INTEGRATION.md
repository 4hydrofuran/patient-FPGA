# A06 → A07 实際核接入说明

2026-10-04：e227297 double核A06离线接收通过。当前源码实际Linux Vitis Csim exit0，61例/2800022检查；源/XO/内嵌XML与必需同版Cosim证据已核验，`KERNEL_SOURCE.json`为accepted=true/frozen=true。只解除A07离线链接前置，不是上板、生产或B04候选验收。A维护接收工具与后续接入；原失败保留在历史证据中。

## 唯一候选及来源

- provider=B，release `b03-a06-supplement-20261003`，源commit `e227297ee1bb0bdf542fc81761642b23639e15c0`，double / build `0xB3030002`。
- 原件：`hw/linear_B_received/B03-supplement-e227297-20261003/payload/`。源码`src/w4a8_prefill_v1.cpp`，头`src/w4a8_linear_v1.hpp`，构建`hls_prefill_double.cfg`。
- XO：`artifact/b03_candidate/w4a8_linear_v1.xo`，SHA256 `96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23`。
- 主XML为XO内`w4a8_linear_v1/kernel.xml`，SHA256 `dadfa622dc114a373af9195778f64e34f4d715ea190426fa745dfd39f818d1de`。外置XML仅序列化不同，hash独立，不能替代内嵌hash。
- 17参数/C类型/寄存器offset/hostSize/bundle完整实测映射：`evidence/A06_acceptance/supplement-v1/interface-map.json`。本轮A修复不改该ABI、源或XO。

## 调用与长度

顶层`w4a8_linear_v1`，`ap_ctrl_hs`。参数0..16依次为W、Sw、Xq、Sx、Y、meta、T、N、K、W_bytes、Sw_bytes、X_bytes、Sx_bytes、Y_bytes、meta_bytes、job_id、abi_version。

T=1..8，N/K=1..4864；Np=ceil(N/32)*32，Kp=ceil(K/128)*128，G=Kp/128。最小字节数依次为Np*Kp/2、Np*G*4、T*Kp、T*4、T*Np*4、40。主机须checked arithmetic并验证实际BO容量，不能只信传入长度。W4[-7,7]、A8[-127,127]，组INT32和按FP32固定次序恢复，不在PL量化。

物理端口宽度W128、Sw32、X128、Y32、meta512、control32；Xq/Sx共gmem_x。AXI bundle不是独立DDR通道，具体bank映射由A07真实平台链接核验，不从本页猜分配。

## meta及错误隔离

meta40B字段offset：magic0/u32、build4/u32、job8/u64、status16/u32、done20/u32、completed24/u64、algorithm_weight_bytes32/u64。magic=`0x57344138`，abi_version=1。

completed读取调用前meta内初值，成功加1；不是独立自由运行硬件计数器。algorithm_weight_bytes仅Np*Kp/2，不含Sw、预扫描或实际AXI事务，不能当带宽计数。

核私有错误0..5：OK、BAD_ABI、BAD_DIMENSION、BAD_BUFFER_LENGTH、NULL_POINTER、INVALID_W4_CODE。主机另验-128、非有限/非正scale、padding、job非0、Y有限。所有失败一律不消费Y；超时保持POISONED与BO所有权直到验证硬件静止。不能假设任意无效物理地址都可被核安全检测。

先同步W/Sw/Xq/Sx和含初值的meta，再运行、等待、同步meta；确认magic/build/job/status/done/count符合当前请求后才同步并消费Y。40B逻辑meta的BO物理对齐/总线越界风险须在平台实现和板测确认，不将内存宽度512bit直接当40B可访问性证明。

## 构建与证据边界

复用Linux2026.1，`source /home/member-a/AMDDesignTools/2026.1/Vitis/settings64.sh`。器件xck26-sfvc784-2LV-c，6.667ns起步约150MHz。宏B02_CACHE_X/B02_AXI_X128/B03_TEST/B03_REUSE/B03_DOUBLE_BUFFER；禁fast-math/FMA重结合。已有XO及其报告可复用，A07直接针对匹配kv260_base链接，不重做优化搜索。

HLS资源BRAM18K110、DSP102、FF20848、LUT35817，slack -0.40ns；不是实现收敛。A07应检查真实布局布线WNS/DRC/CDC和时钟，失败保留。平台/SDK见`platform/toolchain.lock.json`、RA02平台交接和A07独立交叉构建记录。

组数据2176B；down整tile双缓存119KiB是推导，B实际双group槽4352B。P_N32/P_K1/P_T1；T间复用权重与算术并行度分账。局部II1不是全核II1，AXI内部FIFO峰值未测。

Linux/PL内存预算、CMA、BO可达上限、最大常驻和实际bank映射均null/DEPLOYMENT_PENDING_BOARD。BOARD/功耗/实测AXI带宽NOT_TESTED。A11实板数值与恢复、A12全模型消费PL结果仍独立验收。
