# A12 健康检查专项优化报告

状态：PASS_HEALTH_ONLY_BOARD_BOUNDED，限定短输入与自然回答样本，不代表完整A12收口。执行日期：2026-10-24。

## 已完成的三项改动

1. 统一检查调度：许可线程每次仍做新鲜检查；接收主线程只有空闲且最近成功观察超过250毫秒时补检，锁忙时不争抢。观测失败闭锁，不能复用成功旧观察掩盖失败。
2. 同一管理器内保留只读、非阻塞 `/dev/kmsg` FD，逐次读取新增记录，检查64位序号连续性；新警告仍交给原 MinimalGate 判定。EPIPE、丢序/重放、未知分片、解析/读取失败或超出预算均闭锁。初始和生命周期动作边界仍执行原全量dmesg，并逐字节核对新旧来源。
3. 复用三路温度路径，实际温度、boot和内存值每次重新读取；核对路径inode，每秒及结束时复核拓扑。原55°C、MemAvailable1114112KiB、CmaFree98304KiB与完整驻留预算不变。

原每次许可的租约/锁检查、健康观察绑定、JSON持久记录和fsync全部保留。正常卸载、释放和恢复流程不变，ARM程序、数学、权重、公共ABI及B核未修改；沿用原交叉构建产物，本轮没有新HLS/Csim/实现/交叉构建。既有默认CPU选择未改。

## 实板结果

同一A53程序、Qwen3.5-0.8B、24层72投影、TILED双线程、T≤8、1024配置、R0。先CPU后三条PL；GDM对两者均停止。CPU/PL及原任务10产物的token、文本、EOS、最终prefill logits摘要一致；自然回答仍为“疼痛在胸骨后。”。未重新保存逐层原始Y或原始状态，不能把本轮称为新的全层bit-exact诊断。

| 样本 | 旧PL完成秒 | 新PL完成秒 | 本轮CPU完成秒 | 新PL首token秒 |
|---|---:|---:|---:|---:|
| short_profile | 26.488 | 12.812 | 10.738 | 6.837 |
| natural_plain | 124.340 | 64.304 | 73.987 | 52.624 |
| natural_profile | 124.018 | 64.813 | 74.056 | 52.867 |

普通自然回答总耗时由124.340降至64.304秒，减少48.28%；同轮CPU/PL完成时间比1.151。旧/新自然回答prefill首token比较分别92.578/52.624秒，包含管理端请求到首token的普通IPC。短样本PL仍比同轮CPU慢，不能宣称所有请求均加速。

自然回答剖面：健康检查69.202→11.789秒（减少82.96%）；许可等待86.311→27.191秒。保留的租约/锁检查4.089秒、逐次许可持久记录10.409秒，不将这些记为已优化。本轮自然普通模式decode6步共11.647秒（约1.94秒/步），CPU约1.47秒/步，逐字生成仍慢。原许可等待包括健康检查，不能与子项重复相加。

自然剖面期间恰新增1440次新鲜检查，主线程额外补检0次；3240次模型提交的观察时间戳全部不同。整个窗口累计健康锁等待约25.848毫秒，旧窗口未拆此项，不声称精确减少多少锁等待。新窗口自然剖面相对上一样本的kernel区间约8.693秒，温度/内存区间约2.112秒；kernel区间还含原门禁、摘要、归档及日志逻辑，并非纯读取时间。

独立空闲只读30次探测中，增量读取均值0.392毫秒，温度0.552毫秒、meminfo0.204毫秒；旧任务10空闲dmesg33.379毫秒。空闲部件耗时不能代替请求内完整健康耗时（本轮自然剖面约8.19毫秒/许可）。

## 恢复与限制

实际PL调用3240次；72权重每窗口只加载一次，148显式BO共140591104字节，地址/活权重/计数不变。两个worker与manager均exit0，无强杀、强卸载、重启或供电动作；默认PL/GDM恢复，独立及延时FD/VMA/进程/锁后验通过，ZOCL/active lease不存在。归档租约按原字段和字节独立重建，SHA一致，最终完整扫描1次，未用专项finalize票据。

生命周期合并记录LIVE_HEALTH为309条，不是只做了这些次数检查；逐次许可均保存其新鲜观察。最小MemAvailable 3154464KiB、CmaFree 329564KiB，最高温度33.821°C。RSS/CMA不相加冒充整机物理峰值。

本轮仅三个输入≤107token的小样本，顺序未随机化，无p95/统计显著；1022/2048长输入未复测，危险BOARD故障注入未做。自然回答输出6token，短样本为teacher轨迹。纯硬件周期、AXI字节、功耗、整机物理峰值仍null；不是语音或医学审核结论。健康优化未解除R0完整输入重算成本，A12任务11仍未完成，默认FPGA未启用。

## 失败和证据

保留首次派生锚点失败、三版只读kmsg格式核对失败及诊断探测、Windows命令行长度失败。格式问题分别定位到十六进制转义、多行缩进和当前板端非kernel facility的raw显示；修正后probe_04首尾均逐字节一致。codec限定当前已钉住内核和dmesg表示，不能当作通用Linux日志格式保证；不支持的分片直接拒绝。阶段10及更早失败不追改。详见FAILURES.json与各probe/stage原始收据。

PC：11项reader/schedule/path测试（含多种故障子例）和4项实际派生接收器/冻结门禁集成测试通过。历史契约保护、新版配置检查exit0；原任务10封存2547文件逐字节不变。本轮补测没有改原报告、位流或契约。

命令、退出码、脚本SHA：pc_final.json、pc_integration_02.json、probe_04、package_01.json、stage_02、candidate/launch_01、monitor_01/02、readback_01、status_final、delayed_01、audit_01.json及contracts/config_final.json。文件传输使用既有严格主机钉住的OpenSSH，实际上传54736字节并由stage_file_reviewed.py固定SHA读取；下载652741字节回读包由独立extract校验SHA。密码仅输入隐藏交互提示，没有写入文件/参数/环境。

主要数据：BOARD_AUDIT.json、SUMMARY.json、candidate/readback-v1/run-v1/s2/*/client-timing.json、health-metrics.json、worker/events.jsonl、lifecycle.jsonl。代码：platform/qwen35/a12/health_opt.py及独立派生控制器。来源规范：Linux /dev/kmsg ABI，https://www.kernel.org/doc/Documentation/ABI/testing/dev-kmsg 。未提交/推送，子代理0，实际会话模型设置unknown。
