# A12 有界常驻问答：无板交接（2026-10-26）

当前结论：本轮必要无板候选实现与验证收口；整体A12、BOARD、医学审核和生产启用未完成。没有连接板卡、部署、恢复、释放、信号或PL操作。

## 代码及构建

- 新源码为`platform/qwen35/a12/resident_*`、`test_resident_*`。冻结的`promptpl_*`及更早链保持；公共数学/ABI不改。
- PC入口`resident_cli.py`调用`ResidentService`，只允许Linux x86_64软件试验；可信宿主文本ACK不在stdin操作集合中。实际同一进程纯分词，不另载模型。
- PC构建入口`evidence/model_pl_A/20261026-resident-v1/SERVICE_BUILD-v3.json`；WSL工作区`/home/member-a/kv260-build/a12-resident-20261026-v1`。不要重跑已有tag或覆盖目录；DIRTY不能作为重放入口。
- A53原生胶水及控制writer/backend均已编译，原数学DSO/量化对象复用。ARM未执行；默认unbound后端仍拒绝打开设备。
- `resident_board.Manager`及`BoardService`只接实际root ARM64上的原Owner；后者还需明确合成文本试验评审。无Board CLI，没有JSON选择CPU/Board的机制，不创建Owner/租约，不自动finish。
- `BOARD_BUILD-fixed-root-v1.json`是已经PC离线装配核对的`/opt/patient-qwen`目标配置。`resident_layout.py`只在PC新目录放置既有A53字节和原应用；模型/权重及完整普通包未复制。实际放置核对及新Owner签发只能在独立Board窗口做。

## 验证证据

- 最终当前应用源码：`finalcohort1`～`finalcohort7`共25输入；`finalflow`含实际可信历史追问、换病例、重复ID/待确认拒绝；`finalpolicy`为7类策略零模型。
- `capacity01`完成6次模型回答，第7次因原5000总预算的最坏预留而拒绝；`busy01`并发输入在计算前拒绝。它们保留原累计预算，不承诺任意8问。
- 故障：`suite01fbeginfsync`、`suite01fendfsync`、`suite01freceiptfsync`、`suite01fendslow`、`deadline02`、`suite01fappendfsync`、`deliverydeadline01`、`generation02`、`cancel01`。均无应用答案交付；取消例位于活动应用处理、native BEGIN前，不冒称取消了在途DMA。
- `resident_audit.py`重建原计划/可信历史、完整冻结请求摘要、原生结果、日志及图拷贝计数，核对应用END之后的外层新鲜检查。原native内层票据允许在END前取得但须在原250ms内使用；外层票据必须从应用持久I/O后开始。
- `FINAL_CHECK_RECEIPTS.json`记录历史契约、新版配置及20项Python检查退出码；其中6项是损坏原件反例。完整磁盘字节不能单独证明历史fsync成功，故障注入另保留。
- C++真实私有Control/Writer进行9个零数学调用请求、第10拒绝、45个维护状态标志夹具，普通与ASan/UBSan通过。它们不是模型/硬件数值证据。
- PC25输入应用收到至核验返回：min1.250564093、median1.438949619、max2.414721664秒。`cli01`实际管道两次1.512574873/1.381635450秒，startup/warm25.436091609秒；没有Board预测或p95。

## 失败保留与范围

此前pilot01/02/03、flow01/02保留；分别涉及Python作用域、warm checkpoint位置/摘要、旧三请求关闭限制、应用日志epoch字段和测试记录重写。`suite01fgeneration`在会话打开阶段就拒绝，随后`generation02`改为健康会话后触发；原拒绝没有追认为指定场景通过。首次deadline已安全拒绝但原因字段不足，保留并用`deadline02`明确验证。初版审计GRANT字段及内外票据时序预期修正前的源码保留。

C++控制夹具初两次失败保留：首版缺健康初始化/配置握手，第二次没有足够定位信息，不推断其具体原因；带阶段记录的后续普通/sanitizer通过，不能因此删除旧失败。整个A12仍不因PC通过追认ARM、PL、CMA、医学或最终验收。

## 后续板端

先单独核实现场并完成故障处置、旧租约归档和新鲜独立释放，再检查匹配内核/XRT/驱动/PL。原普通资源包先行，随后以目标构建SHA单独绑定候选；原双锁、Owner、完整BO/低2GiB/IRQ与健康门槛不变。Board数值不使用CPU逐字节checkpoint SHA作未经分析的容差标准。

关闭native不等于物理释放；需原Owner完成恢复/finish，之后调用已有最终接口并独立后检。故障保留unknown/DIRTY及Owner，不自动重试或重放。最近仓库记录仍未放行，不能用旧回执表示此刻安全。

详细成果见`docs/A12_PARALLEL_PREBOARD_CLOSEOUT_20261026.md`；最终文件集合及审阅包SHA由`FINAL_REVIEW.json`/`TERMINAL_VERIFICATION.json`封存。复杂实现/证据由主代理完成，Sol仅CLI/doc、DeepSeek仅排版；实际模型设置unknown。本轮无远端整体发布。
