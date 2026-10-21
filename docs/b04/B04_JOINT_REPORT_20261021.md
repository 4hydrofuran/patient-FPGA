# B04 A07 成果接入与无板联合验收（2026-10-21）

## 当前结论

**B04 完整电脑候选的 G1～G6 无板门槛已通过。** A07共享成果已接收并由B独立复核，完整试包已在全新ASCII目录重新编译并通过自测，所有包内输入构建后摘要保持不变。正式候选使用 `B_pc_candidate_v1.zip`，其准确字节摘要和最终整包复测由外部配套收据固定，不由文件名推断。BOARD 保持 NOT_TESTED；具备进入B05的无板前置条件，不代表开发板或整机已经可用。

## 来源与责任

A 原始交付取自 `a/a07-complete-20261004` 提交 `6dd1a93c2fa44b045276c24f4cc79d94e54b88b3` 的 `release/a07_b04_v3/`，接收1,102文件、35,004,532字节。B逐文件核验固定Git blob SHA1，再核验A包内SHA256和43项源码清单。公共契约、HLS源码、私有ABI、实际XO均未变化。

A负责六函数公共调用层、BO和生命周期、目标链接/实现、匹配SDK的ARM64构建。B本轮负责接收与独立复核、实际公共后端控制重建、固定核数值样例和完整候选组装。联合门槛是A已有成果与B本轮证据的合并验收，不声称A本轮重新签字。

## 门槛与证据

| 门槛 | B实际执行或复核 | 状态 |
|---|---|---|
| G1 契约/接口 | 冻结头相同；编译真实核头核对17参数/meta40；实际ARM ELF六导出；源码参数、group_id、同步/meta映射复核 | PASS |
| G2 正常调用 | 未改动A源码：970项主机规则；66笔原始meta与396篡改检查；29控制场景/554断言中的正常、重复、报告、权重所有权；B独立手算核3调用/32输出 | PASS_PC_AND_REUSED_RTL |
| G3 失败路径 | A实际公共后端加原控制传输替身，拒绝陈旧/错版本meta、错误句柄/长度/并发、超时poisoned及不安全释放；B40独立规则、108项job/计数篡改拒绝；A原Linux normal/sanitized各29场景原命令均exit0 | PASS_OFFLINE_CONTROL |
| G4 实现 | 本机xclbinutil重新提取9个实际节，XML/端口/连接、bit/HWH与A原记录一致；复核原routed时序、资源、DRC、CDC与link exit0 | PASS_ORIGINAL_IMPLEMENTATION_REVIEW |
| G5 ARM64 | 原A匹配Common SDK/Cortex-A53生产构建与独立重建记录；B实际readelf读取库/host、六导出及动态依赖；检查生产二进制无控制替身 | PASS_A_BUILD_B_BINARY_REVIEW |
| G6 交付复现 | 全新ASCII目录重新解压、全摘要检查、重编译B profile/probe、A主机/完成记录/实际后端控制测试、B手算核；重新提取xclbin/读取ELF；24项完整候选拒绝检查；构建后输入无变化 | PASS_FRESH_OFFLINE_REBUILD |

收据入口：`reports/b04/joint_20261021/receive.json`、`profile.json`、`private.json`、`pc.json`、`a_preflight.json`、`artifact_review.json`。原始新日志封存于 `evidence/b04/joint_20261021/`；旧B03 RTL/Csim/综合仅按原版本证据复用，不增加虚构事务。

G6试包收据为 `reports/b04/joint_20261021/trial_extraction.json`，联合结论为 `acceptance.json`。正式包最终复测收据为外部 `B04_final_extraction.json`，也在工作区保存为 `reports/b04/joint_20261021/final_extraction.json`。外部收据属于封包后的准确字节验收，不递归嵌入同一个ZIP。

## 实现与平台

实际核时钟149,998,500Hz；原routed WNS +0.809ns、WHS +0.010ns，TNS/THS=0、时序失败端点0；60,541条可布线网络全部完成，错误0。保留93条DSP流水性能警告、18条DSP常量控制建议和2条平台时钟建议，无Critical Warning/Error，不声称零告警。

B核：LUT14,757、FF21,027、RAMB36=42、RAMB18=5、DSP100、URAM0；平台总计LUT27,572、FF40,665，其余上述资源相同。核约占LUT12.60%、FF8.98%、BRAM容量30.90%、DSP8.01%。这些是实现资源，不是电脑仿真内存或运行时占用。

## 验证范围与保留限制

- Windows本轮重建970规则、66归档meta/396篡改和29控制场景，不新增唯一场景数量；没有新Linux sanitizer执行。
- Windows仅以测试专用文件锁适配和真实OpenSSL DLL支持未改动A后端；不以该适配验证Linux锁文件安全标志。A原Linux 29场景normal/sanitized的58份命令逐项核验exit0、stderr无错误和场景身份。
- 控制传输替身不做矩阵计算，不输出FPGA_REAL。B3手算/32输出是独立PC核回放，不能写成端到端PL执行。
- A生产ARM64库和host来自匹配SDK原构建，B重新检查真实文件。本机无匹配Linux Common SDK，本轮新目标编译为NOT_RUN。原A干净目录重建库因路径诊断字符串而hash不同，host相同；不声称库位级可复现。
- 本轮另对实际ARM库/host反汇编，分别读取34,913/565行指令，有限扫描未发现dot-product/i8mm/bfloat/SVE指令特征；库无RPATH/RUNPATH，host仅`$ORIGIN`。该扫描为补充静态检查，不代替ARM执行或穷尽全部指令兼容性证明，见`arm_static.json`。
- 本轮不重新执行HLS、RTL或布局布线。原始A实现/链接证据逐文件摘要匹配，实际xclbin九节重新提取复核。
- 板端、ARM执行、CMA/真实BO预算、带宽、恢复、整机质量、时延与功耗仍为NOT_TESTED/null；真实设备配置保留禁用。

## 失败尝试

Git整分支接收因连接重置失败，改固定提交逐文件接收。第一次PC手算fixture因普通编译器把HLS pragma当错误而停止，后仅对PC核编译忽略不支持的pragma诊断；未改核或数值门槛。复核工具补强期间遇到控制源码清单位置、bash命令回显位于stderr、Windows GBK读取UTF-8日志三个读取问题；均保留说明和原日志，修正后重新执行。

完整试包首次解压到中文路径：B profile、40规则/66meta/108篡改通过，A host970通过；A meta回放因当前MinGW `std::filesystem` 的窄字符路径转换报 `Illegal byte sequence`。生产Linux源码不改动，本机完整控制自测限制为新建ASCII路径并在入口提前说明/拒绝中文目标，后续G6采用全新英文目录。此限制保留，不把中文目录写成完整联合复现通过。

## 下一步

保留正式候选摘要、文件清单和最终解压收据。B04无板开发结束；B05真实上板验证另待平台与开发板条件具备，不恢复已取消的邮件或定时收尾。若后续改变核、公共运行时或候选配置，按变更范围更新摘要并重新验收。
