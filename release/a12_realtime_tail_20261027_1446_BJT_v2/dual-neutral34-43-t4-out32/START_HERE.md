# A12 实时模型长尾优化 v2：独立UNBOUND候选

模型/量化/native/HLS/公共ABI、原checker与评分不变。连续网页加载34-token中性前缀及EXTRA_PREFIX.json所列通用前缀，按完整prompt最长匹配；前缀只含通用词和固定量表满分，不含病例ID或患者评分值。每题评分值与完整答案每个token/EOS仍由本题真实模型计算。普通ordinary窗口仍原3线程/单前缀/24输出；连续线程及前缀长度见profile.json，保持32输出/22320保守逐问额度。

仍只有原允许的两个KV槽（每槽64MiB、合计128MiB），原192MiB前缀预留不变。额外启动预热及总预算见BUDGETS.json；实际保留内存及启动成本见报告。PC验收用--mode realtime，明确不加载答案缓存；正常hybrid模式保留原来源标记，未命中才运行实时模型。

在此目录先做离线检查，不接触设备：

```sh
python3 continuous/fast_response_verify.py --domain PC --bundle . --suite package
```

现有开发机环境的纯实时服务：

```sh
python3 continuous/answer_cache_serve_pc.py --mode realtime --output /tmp/a12-tail-pc-new-001 --port 18771
```

结束时在该PC输出目录创建stop-request.json，并等待正常RESULT.json回执。PC依赖/模型/二进制路径见PC_DEPENDENCIES.json，需现有环境。

BOARD尚未测试，另获实板授权、具备原irq2/登录/空闲条件后，才创建新Owner窗口：

```sh
sudo python3 continuous/fast_response_verify.py --domain BOARD --bundle . --suite web --execute-board --window-id a12-tail-v2-new-001
```

停止整个BOARD服务（结束问诊只冻结评分）：

```sh
sudo touch continuous/stop-request.json
```

等待在途及原Owner恢复/独立释放，再用旧v1独立包开新窗口回退；不要复用已消费授权。无模型权重、SDK/镜像或可重放执行授权。新板端时延/功耗/CMA/计数/恢复仍NOT_TESTED/null。
