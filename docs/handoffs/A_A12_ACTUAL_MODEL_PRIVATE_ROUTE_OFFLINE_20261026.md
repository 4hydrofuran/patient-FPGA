# A12 实际 Qwen 请求入口与 Route 私有协议：无板验证（2026-10-26）

本轮已把双通道授权接到**实际Qwen原生程序的请求生命周期和Route**，完成真实CPU数学路径的R0/warm/hit。最终源码11个场景（2正常、9指定故障）逐项通过独立原件审计，另做4个PC探索窗口与同一活pidfd并发回归。原CPU数学DSO、llama/ggml DSO及既有量化目标对象按原SHA直接复用，没有重编数学库或量化对象。A53实际前端/Route及XRT后端私有ABI编译通过，未执行ARM制品。**实际PL结果消费与板端验收未通过，目标仍active。**

## 实际接线

从原普通包的`main.cpp/route.cpp/route.hpp/bridge.cpp`做唯一锚点、可逐项逆向还原的派生；原件与公共六函数ABI/契约不改。Route实际发出旧router open/close许可，CPU适配器只保留backend open/72次weight_load通道；新私有通道使用前阶段原子页和有界微批协议。

请求参数验证后、任何前缀restore或计算前，前端调用私有begin，把实际wire JSON摘要绑定到本请求代次。每次矩阵调用仍检查页/预算/撤销/期限/T，并保留原CPU实际完成计数和有限Y核验。CPU证明适配器先在至多155648字节的临时Y中完成原数学API，私有complete成功后才复制调用方Y；它不是XRT实现，也没有伪造BO或硬件meta。

实际Route核对只读紧凑完成报告，再逐行memcmp确认已核验结果原样写进模型图；只记两个有界标量，不建立逐投影文件、长ledger或长前缀诊断。原PC输出破坏测试缝放到这次copy检查前，证明坏数据会在custom node返回前拒绝。

成功响应前完成原混合状态清理及私有end；warm保存/restore算法、完整状态/末位置logits格式不变。任何错误调用abort、撤销页和锁存失败，CPU测试合作exit2；ARM保留原未知DMA quarantine行为。正常窗口完成3请求后，实际Route逐一unload/close成功，发`private_closed`并等待ACK；manager确认关闭后停止observer、撤销页、确认原生pidfd终止与所有线程停止，才正常关闭本地验证会话。该ACK不是板端释放批准。

XRT派生库另加私有`A12_PLM_PRIVATE_V1`版本命名空间的begin/end/abort；原公共ABI符号版本保持。ARM的device_open前仍硬返回UNSUPPORTED，正向私有begin/end也UNSUPPORTED，JSON不能开启。CPU数学适配器仅x86_64/SP_A12_PC_TEST可编译，不作为ARM静默回退。

## 真实验证

最终正常窗口各1440/648/792次真实CPU运算，合计2880，图拷贝检查次数逐请求相同；默认未选择CPU context的运行/权重计数均0，实际路由CPU权重常驻72份，无fallback。自然生成、EOS、token、文本、末位置logits SHA/FNV及清理状态均与冻结普通CPU基线一致；命中恢复70 token，只新算37 token。

warm在实际内存中计算并报告的state/sequence/logits SHA、字节、70 token和position69也与原冻结CPU窗口一致。这只证明所列实际快照摘要及普通输出范围，**不冒充新增全层/全位置中间值原件比较或PL数值验收**。原完整中间值证据按旧范围保留，没有重扫4542份原件或在板端制造新缓存压力。

11个最终场景包括cap1/cap72正常、BEGIN/GRANT/END/receipt fsync失败、GRANT/END慢日志导致旧ticket过期、wire摘要改变、图输出拷贝破坏、缓存第5次claim撤销。故障不以“任意错误就算通过”：核对指定reason、实际claim/CPU/copy计数及错误包；均0可交付结果、保留DIRTY/撤销页/所有者FD、不自动重试/释放。

第5次claim撤销场景中，实际CPU forwarded/verified各4，图copy_checks4，claims5且unknown保留；第5次CPU运行未开始。图拷贝破坏在claims1/CPU1/copy_checks0拒绝，原生错误明确`private graph copy differs`。完整END/receipt字节即使存在，fsync失败或之后ticket过期仍不交付。

独立审计读取真实native stdout、私有WSL原件及镜像当前字节，检查严格JSON、链/顺序、wire摘要、冻结请求/预算/T范围、实际CPU计数、Route copy检查、token/EOS/内容、状态清理、回执和交付fence。普通配置仍profile=false、logits_mode=final、无diagnostic_dir/dump_state/state_fingerprint/a12_consumer_trace，无`.bin/.f32`长诊断文件。

## 保留的失败与纠正

- 首版适配器编译缺OpenSSL头，原生前端已构建但适配器失败；沿用已有A07 PC header缓存补齐include，没有安装、重装或升级依赖。原错误收据/工作目录保留。
- 开发套件的缓存撤销窗口因共享Python poll对象被observer/service并发调用，启动阶段claims0提前失败。旧套件曾因过宽“失败即可”的判据记为预期结果，现明确**NOT_ACCEPTED该目标未触发**，不改旧记录。新实现每次使用独立poll对象，观察同一个已持有pidfd，不按PID重开。8线程×200次真实并发回归中，旧实现1400次冲突，新实现0；同一pidfd在进程实际退出后拒绝。
- 收紧各故障的特定原因/计数/原件条件后，完整最终11场景重测通过；不能用提前退出、别的错误或旧源码结果替代。

## PC时延探索

已知编译任务终止后做cap1→cap72→cap72→cap1四个窗口，各模式仅2个样本：

| 冻结请求，发送到通过结果交付门禁的均值 | cap1严格控制 | cap72微批 |
| --- | ---: | ---: |
| 普通R0 | 10.021 s | 3.648 s |
| 前缀hit | 5.368 s | 1.720 s |

每个窗口工作量均2880次实际CPU运算，计算grant数2880→40，总许可消息2956→116。测量到内容/状态/END/receipt/新鲜健康门禁线性化点，不含随后审计JSON写入、启动/模型加载、UI、网络或语音。raw native first-token只用于内部观察，未把未核验token当作用户已收到的回答。

这些是**PC小样本描述，不是板端收益/P95/统计显著性或SLA**。主机负载未控制，独立原件审计可能与第一探索窗口部分重叠；早先开发对照还与交叉编译并行，因此不作为正式性能验收。控制协议成本可减少，但KV260实际耗时仍需普通PL路径实测，不能直接套用这些秒数。

## 制品与尚未完成

审阅包：`evidence/model_pl_A/20261026-model-route-v1/actual-model-route-offline-unbound-v1.zip`，SHA `f45d4007e262cf1fed4ea9b80d00361be5f89780a439e0c054a55d65389a512d`。包逐成员CRC和SHA回读通过；仅含派生源、PC/ARM编译制品及数学引用，不含GGUF/sidecar/真bitstream/安装恢复上板脚本，不是独立运行部署包。原普通`bundle-v2.zip` SHA仍为`acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`，仍为未来恢复并确认安全释放后首轮板测基线。

**仍需无板推进：** 独立live boot/lease/双锁/driver/kernel/BO-generation批准的校验与消费；把实际模型新协议接到PL模式协调器、未知在途及新窗口严格回退。当前仅冻结3请求验收窗口，不能宣称无限请求SERVICE已就绪。实际PL结果消费、普通资源轨迹、最终数值/生命周期/A12 step11/长期/医学验收仍按未完成保留。

没有上板、SSH、恢复、刷写、部署、释放或推送；B/HLS、公共数学/ABI、原安全门槛和既有失败保持。BOARD NOT_TESTED、SERVICE=false、CMA/板端时延收益null。复杂核心、设计和证据验收未委派，未使用DeepSeek；实际agent模型设置unknown，不声称已切换。历史契约与新版配置guard均exit0。
