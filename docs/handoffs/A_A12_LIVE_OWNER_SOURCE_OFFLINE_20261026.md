# A12 原有Owner/Platform代次来源接线：无板进展（2026-10-26）

本轮把原生代次页的上游补成可复用的live-source绑定组件，并实现**连接冻结原件Owner/Platform的BoardPorts准备代码**。当前没有Board Owner、租约或批准被创建，没有ARM执行或板端连接。实际Qwen验证仍是CPU数学与明确标识的设备/CMA策略夹具，不能称真实设备安全或PL验收通过。

## 接线与性能边界

- BoardPorts只接收私有命名空间加载的原Owner，以及包裹原Platform的确定类型；要求注册root ARM64、精确machine/kernel/boot、现有原租约及5000次/72权重/140591104字节预算。它不创建Owner、获取租约或打开DRM设备。
- 启动前复用原完整无用户/引用、IRQ、拓扑和全BO待分配admission；驱动哈希按原流式函数只在代次建立时校验。常驻后启用原already_charged计费，避免把已分配BO重复扣减；新来源不重复扫描权重、长前缀或中间值原件。
- 周期沿用原Owner串行kernel/温度/内存门槛；CmaFree≥98304KiB、MemAvailable≥1114112KiB及温度/日志连续性规则不变。原租约每轮仍全量新鲜SHA一次，在前后加持有FD/规范路径/元数据锚定，省去同一租约的第二次哈希；未缓存可变文件的通过结论。
- 模块、overlay、driver绑定和render节点通过O_PATH保持当前dentry/inode身份，O_PATH不打开DRM驱动。相同文本/UUID重新建节点也不能继承旧代次。较大文件不进入周期或逐投影热路径；machine-id及属性读取均有界。
- 原生context摘要还要匹配实际持有pidfd/Popen的PID/起始ticks、xclbin UUID/SHA、build/device/groups/windows及4个IO地址。Board路径在消费批准前独立核对native继承两把规范FLOCK。READY再运行原148 BO/72权重/140591104/8192对齐/低2GiB/不重叠规则并绑定最初IO代次。
- 能力为单次内存对象，JSON、复制对象、错context、重放和过期均不能消费。所有Source失败先撤销共享页，再返回错误；不清unknown、不自动重试、不产生释放批准。复用已有4096字节页，仍使用384字节，不增加CMA BO。

## 平台变更互锁

新Platform派生同时覆盖原PL/驱动command和另一路直接subprocess的GDM service；原allowlist、guard、核日志前后检查及命令执行体均继续由原方法执行。绑定来源后，变更尝试首先原子撤销，再检查真实native已正常终止及持有只读页无active/unknown，最后调用原fresh no_users门槛。模块存在时仍要求原refcount0；确实不存在时复用原absence分支，未把None当0。

退出pidfd本身不是释放依据，还须正常exit0和真实页无active/unknown。新增O_PATH观察句柄在授权撤销后，或正常原生结束且页已知空闲后关闭，不接触原租约/双锁或native设备/BO；这样不让仪器本身阻塞原释放扫描。Board借用lease/page观察FD仍要等原恢复/最终finish完成、原锁列表已由原流程清空且interlock已退休，才能关闭。随机epoch与单调变更serial不允许原平台对象重新绑定新批准。该协议依赖协作进程/原唯一租约，不能宣称防住绕过这些入口的恶意root直接重编程。

## 无板证据

最终33项实际Linux句柄/策略用例通过，含两把真实FLOCK继承、inode更换、同UUID节点重建、能力重放、旧回执不能替代新释放、健康下限、原BO反例、原lease完整SHA只执行一次及恢复无模块分支。测试节点和CMA数值明确为PC夹具；没有真实BO分配。

普通及ASan/UBSan各22项原生断言通过；PC正向Board签发ABI始终返回null。A53管理端签发库交叉编译通过，须精确root/machine/kernel；它不映射XRT。实际原生/CPU/XRT消费者和数学DSO/量化对象按原SHA复用，公共契约无改动；现有A53 XRT消费者的device_open仍硬返回UNSUPPORTED。

实际Qwen最终5窗：cap72/cap1正常、同UUID节点重建、活动PL变更、BEGIN fsync失败。正常各2880真实CPU调用，grant分别40/2880；私有通道41/2881、旧通道75不变。新来源仅增加两个窗口级绑定/常驻记录，没有逐投影新日志。

两个代次故障均确定到claims5、实际CPU启动/核验4、图拷贝4，0可交付结果，unknown和DIRTY保留，CPU合作exit2。活动变更未进入释放或命令执行；同UUID重建在旧租约/JSON检查仍通过时，被新持有节点身份拒绝。BEGIN fsync失败claims0。独立审计读取实际stdout、WSL原件/镜像、链/顺序、Source指纹与节点inode、冻结token/文本/EOS/logits、warm快照摘要、清理/回执及交付门槛，未冒充全中间值或真实PL验证。

## 阻碍与修复

冻结工程的绝对导入与现有根模块同名，首次导入被拒绝；现改为私有命名空间，仅限定本地import名称。逐模块逆向AST与原件一致，原阈值/断言/方法体不改；导入测试禁止命令、网络和/proc/sys/dev等设备来源访问，没有创建任何原Owner/Platform。原sys.path、环境与根模块对象保持。-O会移除原断言，因此明确拒绝优化解释器运行这些门槛，未放宽原断言。

首轮独立审计新增分支误用原RESULT变量名导致KeyError，保留失败；改为独立source_meta并完整重跑审计。随后发现原释放函数会把新增render O_PATH也计作设备持有者。用v1审阅包原源码、实际本进程FD表的PC proc代理和显式私有文件别名复现：旧候选正常结束后仍报ACCELERATOR_DESCRIPTOR_STILL_OPEN。修复后原函数原样通过，原租约/双锁仍持有；exit7仍拒绝正常完成。该代理/别名/引用0是明确PC夹具，不代表真实板端释放。

另做8线程1600次close/FD复用无误伤验证，并实际持有观察锁，确认原子页撤销已可见而清理线程仍等待锁。未豁免O_PATH、未清unknown。v1包和旧审计完整保留，明确NOT_ACCEPTED_FOR_RELEASE_INTERLOCK；修复后最终使用model03五窗、v6检查及独立审计、反例与并发证据，v2包才是本轮候选。相关失败见IMPORT_FAILURE-v1.json、AUDIT_FAILURE-v1.json及OPATH_RELEASE_COUNTEREXAMPLE.json。

## 制品与未完成项

审阅包`evidence/model_pl_A/20261026-live-generation-v1/live-owner-source-offline-unbound-v2.zip`，SHA `38e4aea2f0398fab2fb89e9cff1d0c6beb342c00f87550b69eebfabae32495dc`，逐成员CRC/SHA回读通过。包含准备代码和管理端PC/A53库，依赖冻结仓库/原native、库及模型；不是独立部署包，不含模型/sidecar/bitstream/安装恢复或上板执行脚本。原普通资源包SHA仍为`acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`，仍是将来首轮基线。

**仍需无板推进PL模式协调器**，包括真实Board provider/native manager、继承双锁与原Owner worker/finalization接口，完整未知在途和显式新窗口严格FPGA回退；随后按原要求做总完成审计。当前仅冻结3请求验收窗，不能称SERVICE就绪或无板全部完成。

本轮无新增可预测板端时延的数据，Board耗时/CMA均null。原故障、短提示词失败、门槛和公共数学保持；不上板、不SSH、不恢复/释放、不推送。模型/effort实际设置工具不可核实，记unknown；核心逻辑与证据验收未委派DeepSeek。目标active。
