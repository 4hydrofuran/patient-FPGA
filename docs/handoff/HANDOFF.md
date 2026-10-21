# B04 无板候选交接（2026-10-21）

工程 `D:\KV260-project-HLS\b_qwen35`，分支 `b/qwen35-compute`。B04按已采用的A07/B04分工完成无板门槛：A的公共六函数/XRT生命周期、目标链接/实现和匹配SDK的ARM64产物，与B本轮独立复核及新目录重建证据合并。当前入口为 `README_B04_CANDIDATE.md`、`docs/b04/B04_JOINT_REPORT_20261021.md` 和 `reports/b04/joint_20261021/acceptance.json`。

A原始包取自提交 `6dd1a93c2fa44b045276c24f4cc79d94e54b88b3` 的 `release/a07_b04_v3/`，1,102文件，Git blob及包内SHA逐一核验，保存在 `evidence/b04/a07_received_20261021/`。B03 double源码/XO/ABI与公共契约未变化；build_id `0xB3030002`，meta40，XO SHA256 `96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23`。

本轮新执行B40规则、66归档meta/108篡改，A970主机规则、66归档meta/396篡改、29控制场景/554断言及B手算核3调用/32输出；没有新RTL事务。实际xclbin九节、真实ARM ELF/导出/依赖与原routed报告复核通过；A原Linux sanitizer和SDK/干净重建证据按原范围复用，不冒充本机新Linux/目标构建。

完整试包新目录复测通过，正式文件为 `B_pc_candidate_v1.zip`。正式ZIP准确摘要与最终重建绑定外部收据 `B04_final_extraction.json`；工作区同一记录在 `reports/b04/joint_20261021/final_extraction.json`，不将外部最终收据递归塞进自身ZIP。

Windows完整控制复现要求ASCII解压路径；中文试包的MinGW文件系统转换失败已保留，B独立探针中文路径通过。Windows文件锁适配仅用于控制测试，不修改A生产源码。所有真实设备配置继续禁用；BOARD、ARM执行、真实BO/CMA、带宽、恢复、时延、功耗和整机质量未测。

下一步为B05：待实际板卡及匹配平台条件具备后开展独立板测。本轮不触发上板、邮件或定时收尾。旧B00交接已按原内容归档到 `history_handoff/HANDOFF-20261002-000000.md`；旧部分包、失败尝试和B03历史证据保留。
