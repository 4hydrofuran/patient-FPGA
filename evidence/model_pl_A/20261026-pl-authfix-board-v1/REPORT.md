# A12 授权字段修复与普通 PL 验收（2026-10-26）

结论：**FAILED_PL_ACCEPTANCE_ATTEMPT**。

修复将工作量 spec.authorization_included 保持 false；计算授权单独绑定原 Owner review。新增绑定函数复用原 validate_plan，并在驱动/PL 加载前完成工作量校验；不放宽原策略。旧错误脚本、失败窗口与冻结包不覆盖。

定向 PC 验证：历史契约、新版配置、两项授权回归、一项普通三请求控制链测试均退出0。控制链测试使用明确的替身，不算PL证据。

用户授权本轮一次正常重启和一次临时 irq2 引导，实际各一次；无刷写、saveenv或默认启动文件更改。第一次重启入口因旧租约拒绝，实际未发送重启；旧启动的失败租约在锁与原占用检查后原样归档。

串口登录等待超时及提示符重新获取失败保留；首份超时记录的登录输入已脱敏。另有本机报告编码失败，修正为显式UTF-8后继续；这些步骤均在本轮PL计算启动前。

实际启动：`0978088a-8d10-45b2-8f43-726d00209313` / `6.8.12-a10irq2`。原普通工作量为 R0 / warm / hit，107 / 70 / 37 个新提示词 token，输出上限8，72权重加载和5000总提交上限保持。未新增长前缀诊断、全状态导出或历史原件扫描。

## app_R0

```json
{}
```

## warm_prefix

```json
{}
```

## app_hit

```json
{}
```

普通R0/hit比较：None；管理器退出码：None；平台恢复：False；活动租约：True；ZOCL：True。

通过范围仅为这一组普通模型输出、前缀复用和资源流程；不追认为全面数值验收、长期稳定性、常驻候选服务或生产可用。硬件全局计数仍null；提交数是原权限/后端完成证据。

证据：RESULT.json、PC_CHECKS.json、BASELINE_REVIEW.json、boot-after-archive.json、start-uart.json、collect-uart.json、board-receipt.zip及解包目录。
