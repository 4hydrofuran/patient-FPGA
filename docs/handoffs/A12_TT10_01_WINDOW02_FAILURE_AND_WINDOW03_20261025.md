# 20261025-v2：CPU旧格式比较失败，关闭与独立后检通过

用户明确授权按v2计划先检查再执行。此前两次GUI认证失败payload_sent=false、板端脚本未发送；后续按用户指示改为本会话内存认证，SSH/sudo已实际成功，不再弹窗。未把凭据写入文件、argv或环境变量，未取消SSH服务器认证或固定主机密钥校验。

## 实际执行与通过项

新鲜基线/资源/命名空间及实际双锁探测通过，boot1d0499ab-f1f9-438c-969a-3e701a0d806f、6.8.12-a10irq2；完整内核原始字节SHA e6c899a5780c7c6c6549ff11fa8940654665ba699e4c5e85c088fbb5f401069e与前次已审查记录完全相同。已知启动限制保持OPEN，新增诊断不豁免。初次MemAvailable=3246400 KiB、CmaFree=782832 KiB；执行入口再次检查3262064/779456 KiB，均通过原门槛。协调锁、部署锁和设备规范锁均真实非阻塞取得并释放；随后新管理器建立唯一新租约。

只执行这一个v2窗口。管理器4112/CPU worker4211已在板上运行source-04原生程序（SHA115d167265667f026594836760be12470876e2b001b9dc8b61773459da35efab）。CPU第一个diag_exact产生正常OK结果，随后旧结果格式严格比较断言失败，未进入warm_prefix和实际PL阶段。原管理器exit1、外层驱动exit2保持失败；run-v1/result.json为FAIL_CPU_STAGE_NORMAL_FINALIZED，compute_pass=false。

CPU关闭通道在真实板上完成已登记身份/FD/maps复核、合作SIGUSR1与stdin shutdown、worker正常exit0、独立关闭健康观察、默认平台/GDM复核及租约归档。计算失败锁存和最后计算成功时间未重置，没有强杀、重启或PL操作。关闭第一次完整扫描因PID1的FD/进程集合变化不完整，原记录保留；按原有有界观测规则第二次扫描完整通过，没有把不完整扫描当PASS。管理器自然exit1保留失败。

额外独立SSH只读后检exit0，确认无活动租约、双规范锁无持有者、完整FD/VMA扫描通过、内核连续性允许、默认overlay applied、GDM active、ZOCL absent。此处通过的是本次CPU故障关闭/释放路径，不是TT10-01计算BOARD验收。

## 失败原因与严格证据

本次444个诊断原始文件与TT10-00 CPU旧对照文件名、长度、SHA全部相同，包括全部投影、logits和prefill hybrid-state.bin。旧结果没有last_prompt_logits_sha256，旧state_fingerprint只有bytes/FNV64；新版新增SHA字段，通用严格same_result因此按缺项拒绝。没有数值容差，也没有改写这个失败。

旧末次prompt logits SHA可从旧logits-prefill-8.f32独立重算；旧终态指纹是decode后的20325212字节，prefill hybrid-state.bin为20312900字节，不能拿prefill字节冒充旧终态或填造旧终态SHA。缺失项明确NOT_AVAILABLE。LEGACY_FAILURE_DIAGNOSIS.json逐件保留444个参考/实测哈希及严格比较差异。

原始回读40630741字节，SHA f3fcc36102a67da2e29ad9354e23e197eeda02ad3dc847407e09442b19f9dd15，473个文件独占解包并校验，包含全部已执行诊断原件及关闭/权限/健康记录；板端原件也保留。原stage preflight、manifest、stage receipt、归档租约另按base64/长度/SHA完整取回，未从候选数据补造旧参考。

## 后续修订，只在电脑端准备

独立v3包window-20261025-v3/bundle-v4已准备，未部署、未执行。旧格式桥接只核对旧参考确实存在的全部必需字段、原终态bytes/FNV64及全部444原始文件，并从旧raw独立推导末次prompt logits SHA。旧终态SHA仍标记无法核验，不追认；新R0/hit完整SHA/状态比较函数原字节保持不变，缺项/不一致仍拒绝。原生程序、管理器关闭通道、数学/ABI、6请求、资源门槛与5000硬上限/4752最坏预算不变。只新增桥接模块、修改legacy分支与新window ID；legacy-case.patch可审查。

以本次保存的真实ARM原件及字段损坏/缺项负例完成14项PC检查，v3隔离导入、默认PLAN_ONLY及清单检查通过；模型运行0，source-03未重跑。它是事后兼容层修订，不把v2原断言或计算状态改记PASS。v2为已消费窗口，按其计划“不能因退出1自动重跑”；若继续，需另行明确授权这一具体v3独立窗口并重新检查现场。

## 未通过或尚未执行

PL阶段、普通应用R0/hit、70/107token诊断下的实际CMA余量及真实少算/TTFT均未执行到，不能宣称原CMA问题实板解决。旧终态SHA历史证据缺口保留；V07/V08质量拒绝与教师审核PENDING保持。TT10-01仍未完成，新增PL调用0，实板应用TTFT=null，≤10秒未验收，TT10-02未开始、A12第11步PENDING。DeepSeek未参与调试或证据验收，实际模型设置unknown。
