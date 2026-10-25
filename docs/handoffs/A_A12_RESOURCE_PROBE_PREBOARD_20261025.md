# A12 普通 R0/warm/hit 资源探测包：无板交接

日期：2026-10-25。状态：**PC_PREPARED_UNBOUND_WAITING_BOARD_RECOVERY_AND_NEW_AUTHORIZATION**。

按用户要求，先完成无板代码和验证，板测等待当前故障恢复、安全释放确认后单独执行。本轮无 SSH/串口/JTAG/板卡读取或恢复操作，新增 PL 调用为0；不继续旧 CMA 读取端候选、不改原失败或默认后端。

## 最终产物

- 探测包：[bundle-v2.zip](C:/Patientqwen/evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip)，8325748字节。
- SHA256：`acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`。
- Manifest SHA256：`4fcb6af2d9e7d5b89f876697de6bd8f11e36174666169544a9016009551f070f`，165个文件。
- [报告](C:/Patientqwen/evidence/model_pl_A/20261025-resource-probe-v1/REPORT.md)、[包记录](C:/Patientqwen/evidence/model_pl_A/20261025-resource-probe-v1/PACKAGE-bundle-v2.json)、[管理器差异](C:/Patientqwen/evidence/model_pl_A/20261025-resource-probe-v1/MANAGER-bundle-v2.patch)。v1包及全部历次测试记录保留。

## 行为和安全边界

新编排仅执行 `app_R0 → warm_prefix → app_hit` 一组。采用旧冻结输入107 token、70-token中性前缀、命中后新算37 token及相同短回答上限；新短提示词未混入本包。应用Session、路由、模板和内容检查使用冻结版本，不读取工作树已改变的默认提示词。

普通与warm均为末位置logits，无全层转储、全位置logits、状态文件、细分profile或消费者追踪。不会调用 DiagnosticReader、旧原件比较、FILE_HASHES遍历或历史归档缓存整理。真实前缀快照/身份与恢复检查、每投影BO同步/meta/输出核验继续由原生版本完成。

保留原 MemAvailable≥1114112 KiB、CmaFree≥98304 KiB；前缀准备仍额外保留192 MiB规划余量。72份权重、148个显式BO、140591104字节预算、低2GiB地址范围及8192对齐保持。最坏3024次提交，原5000次硬上限、72次权重加载和1800秒会话边界保持。无自动追加请求/重试。

资源观察只在阶段边界，独立日志最多24行、每行8192字节；通常8个边界观察，采集CMA/普通内存、RSS/PSS、提交与加载次数。请求发送前的观察包含在应用时钟中。原逐投影新鲜许可、健康和fsync未优化/未跳过。低资源、健康失败、错误完成/状态、日志故障或关闭超时立即锁存，保留所有权，不自动强杀/卸载/清缓存。

原source-04 ARM程序、库、硬件、应用等46个关键载荷文件与父包SHA相同。管理器使用冻结cpu01管理器的既有PL生命周期，去掉CPU长链及历史归档读取；安全类/助手AST不变，正常释放/卸载/默认平台恢复代码段逐字节相同。故障恢复能力没有因本次准备而新增PASS。

## 实际无板验证

1. 历史契约保护、新版配置检查均exit0；旧契约仍DRAFT，runtime/BOARD仍NOT_TESTED。
2. 最终21项Linux PC控制测试通过：资源边界与前缀余量、发送前拒绝、错误计数/状态/后端/logits、请求变更/重放、日志同步故障/路径替换/容量、关闭超时、包路径和无执行入口等。管理器隔离导入采用审计钩子拒绝进程/网络/板端路径访问，通过；直接main在首次板端检查前拒绝。
3. 最终包的真实x86 CPU模型R0/warm/hit通过：相同输出token/text/EOS、末位置logits FNV及SHA、活动状态清理；复用70、新算37 token；两个worker正常exit0；原始诊断文件0。仅PC流程证据，不能折算板端时延或CMA回收。完整中间状态本轮不重测。
4. 父包168份文件及5份公共契约文件SHA/长度不变；ZIP CRC、清单和46份关键载荷保持性通过。

测试记录：`pc-tests-03/`（21项）、`native-PC-02/`（真实模型）和`STATIC_REVIEW.json`。早期18/20项测试与native-PC-01均保留；不是额外独立板测次数。

复核发现旧TT10-00计时助手将cache固定标为R0。v2只将该字段改为原生实际cache信息并绑定身份，保留原计时边界；没有更改采样/数学/数值标准。

## 默认入口和后续执行条件

本包只有本地审查入口，可在仓库运行：

```powershell
python -B C:/Patientqwen/platform/qwen35/a12/resource_probe_entry.py --bundle C:/Patientqwen/evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2 --plan-only
```

包内同样路径可在解包根目录执行。它只校验新包自身的32MiB左右载荷，不扫描旧诊断或访问板端。没有`--execute`命令。

管理器保留显式UNBOUND拒绝；控制preflight的boot/kernel为null，activation为false，backend.pending允许设备访问为false。**本交付不是已绑定的板端驱动，也不包含任何计算授权。** 后续必须先确认当前故障已恢复、独立安全释放，再做新鲜身份/boot/内核/完整FD/VMA/锁/资源审查，取得新计算授权，审查独立绑定驱动和新manifest，并接上既有独立/延迟释放后检。不能删除一行拒绝就自行运行，不能沿用旧v3授权或历史恢复记录。

PL资源失败时现有保留所有权语义仍存在；本轮不把“无在途DMA已证明的关闭”推广为任意PL故障自动释放。BOARD、CMA改善、应用时延均NOT_TESTED/null。A12第11步、TT10最终验收、教师审核和新短提示词验收保持未完成。
