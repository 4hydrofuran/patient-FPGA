# A12 无板交付：2026-10-27

已完成方案 N0～N6。默认选择 **short34-threads2**，旧 70-token 回退和独立 3 线程候选也已准备。三个 profile 各自包含 ordinary 与 continuous 两种独立窗口，均为 UNBOUND；不携带可重放计算授权。

| 产物 | 当前验证 |
| --- | --- |
| [short34-threads2](short34-threads2/START_HERE.md) / [ZIP](short34-threads2.zip) | 真实 CPU 网页路径 25/25、7 策略零模型、3 组 R0/hit、同场两问与 20 分冻结通过 |
| [legacy70-threads2](legacy70-threads2/START_HERE.md) / [ZIP](legacy70-threads2.zip) | 原默认提示词与 70-token 接线回归、离线完整依赖和预算检查通过 |
| [short34-threads3](short34-threads3/START_HERE.md) / [ZIP](short34-threads3.zip) | 独立线程身份和离线依赖/预算通过；未运行新的 3 线程 CPU/Board 模型生成 |

34 项网页单元/接线测试、6 项原授权绑定回归、15 项真实本地 Edge 浏览器协议替身检查均通过。详细命令、退出码、失败保留及源码摘要见 [报告](../../evidence/model_pl_A/20261027-fast-response-v1/REPORT.md)。包和逐文件摘要见 [ARCHIVES.json](ARCHIVES.json) 及各 profile 的 MANIFEST.json。

在现有 WSL 环境复核主候选，不接触设备：

```sh
cd /mnt/c/Patientqwen
/home/member-a/kv260-build/a12-fast-response-20261027-venv/bin/python -B release/a12_fast_response_20261027_v2/short34-threads2/continuous/fast_response_verify.py --domain PC --bundle release/a12_fast_response_20261027_v2/short34-threads2 --suite package
```

每份包自己的 START_HERE 提供单一启动入口、停止和回退命令。板测另行执行 B0～B4：先独立普通短提示词 R0/warm/hit，正常恢复并确认释放后，再开连续网页窗口。连续窗口输出 24/context 1024；34-token 最坏逐问预留 **10584**，本次冻结普通代表请求配对最坏 **4320/5000**。8 个模型问题和 2 个策略问题的顺序见 BOARD_SEQUENCE.json。

本轮没有连接板卡、启动 Owner/PL、刷写、重启、改 HLS/公共数学/ABI或推送。真实 PL 的 34-token 命中、板端内部首 token、可见核验回答、功耗/CMA/硬件计数和正常释放仍为 NOT_TESTED/null；没有宣称达到 10 秒。原有实板历史 PASS 保留。

源码与证据增量见 [engineering-increment.zip](engineering-increment.zip)，供现有仓库合入；部署使用上面的 profile ZIP。源码/文档/命令与包摘要见 [ENGINEERING_ARCHIVE.json](ENGINEERING_ARCHIVE.json)。

阶段推荐均为 High；工具无法核实或切换实际推理设置，记录 unknown。新增 Python 依赖仅安装到本任务独立 WSL 虚拟环境，版本见 [PC_ENVIRONMENT.json](PC_ENVIRONMENT.json)；未全局升级工具或依赖。
