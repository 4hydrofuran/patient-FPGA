# 二十例随机病例：实板运行交接（2026-10-27）

已完成部署并在板端保持服务运行，记录时刻2026-10-27T21:40:34.735645+08:00（北京时间）。点击“随机抽取并开始”，服务端从20例中随机分配一例；页面已移除病例下拉框。刷新和相同请求重试保持本场病例，结束后点击“抽取新病例”再次抽取。独立随机抽取允许再次抽到相同病例，不承诺无重复。

运行窗口：`a12-case20-random-20261027-v1`；目录：`/var/lib/kv260-a12/case20-random-20261027-v1`；boot：`98886b24-96d3-409e-a783-ce9c54873da9`；kernel：`6.8.12-a10irq2`。原Owner与模型进程为用户使用而保留，当前不应清理租约或再次启动窗口。本轮没有重启、刷写、更换模型/native/HLS或重建SDK。

记录时网页ready=true、busy=false，1320条答案目录已启用；新场次为`8b5873ed7e58446dbd00c3951cc7a69e`，尚无问题，供用户直接使用。活动Owner PID 8683、模型 PID 8766；剩余约3.90小时属于本次有界窗口，非永久常驻服务。

| 验证 | 实际结果 |
| --- | --- |
| 电脑端随机/重试/刷新/结束后重抽 | 2项针对回归通过；实际Edge三场抽到20、13、15例，答案缓存正常 |
| 板端首条真实FPGA回答 | 随机第18例，“疼痛在什么位置？”→“疼的是左前胸。”；MODEL/FPGA_REAL/EOS/checker通过 |
| 首条板端真实模型耗时 | 网页轮询采样13.104秒；native 12.859秒；实际34-token前缀命中 |
| 板端Firefox可见窗口随机/刷新/缓存 | 三场分别抽到11、8、16例；完整回答两次rAF绘制133、137、142ms |
| 缓存来源与计算 | 三条均MODEL_CACHE/原CPU_REFERENCE，model_called=false；模型结果数量始终为1，无新增模型请求 |
| 最终用户场次 | 已重新随机抽取，0条问题，保持就绪 |

133—142ms仅是三条实板缓存样本，不是所有输入保证；未命中仍执行实际模型，本轮样本约13秒，不宣称实时FPGA计算低于1秒。

空间记录：目录1,732,636字节（1.65MiB），实际加载1320条。单34-token公共前缀保留21,614,659字节；管理进程RSS 70,892 KiB、模型进程RSS 555,196 KiB。记录时MemAvailable 2,285,280 KiB、CmaFree 55,392 KiB。MemAvailable及CMA为即时观测，不能视为固定可分配上限。原共享DDR/BO准入逻辑保留，没有为20例复制模型状态。

旧三例窗口v7已通过原Owner正常关闭：worker exit 0、1440次许可及完成一致、租约归档、ZOCL卸载、默认平台applied。两条用户问诊先保存快照并随原会话归档，未覆盖。旧Owner结束后仍保留结果页端口且屏蔽SIGTERM，因此仅在已释放硬件后终止该只读结果页进程3253；旧Firefox以SIGTERM退出，没有杀在途模型。

通过固定COM5通道接收与检查，使用已有以太网192.168.2.1直连传输；板端临时增加192.168.2.2/24，保留原192.168.137.2/24及路由，没有写持久网络配置。上传到独立staging目录，核对包SHA及1925项文件。源包SHA256：e8536e0ff736f97f574afb1d99b92d386cb5365c7d34dc3ccb9a278c05bd201a。旧包及问诊记录保留。

应用请求的变更已显式记录为UI_RANDOM_CASES_V1：POST /ui/v1/sessions仅提交request_id，不再接受学生指定case_id；旧请求最小反例返回400。GET /ui/v1/cases现在返回随机策略和病例总数。应用响应仍有内部case_id用于记录与评分，原计算/语音契约及fixtures字节未改。详见本轮API_CHANGE.json和针对回归。B原件只读；A派生源码位于`platform/qwen35/web/integrated/B_601e69ca_A_case20_random_20261027/`，准备脚本为`platform/qwen35/web/case20_random_prepare.py`。

当前源候选：`release/a12_case20_random_board_20261027_v1/case20-random-t4/`；当前状态以CASE20_RANDOM_SOURCE与本轮LIVE_HANDOVER为准，继承的旧基线元数据只用于历史追溯。
证据：`evidence/frontend_board_A/20261027-case20-random-v1/`，重点为LIVE_HANDOVER.json、board-receipt/WEB_REAL_VERIFICATION.json、board-receipt/CASE20_RANDOM_BROWSER.json、old-release.json及stage-board.json。

结束问诊只冻结本场评分；停止整个服务需向`/var/lib/kv260-a12/case20-random-20261027-v1/continuous/stop-request.json`写请求，再等待原Owner完成关闭、恢复和释放。本轮新候选已改为原Owner释放后立即关闭HTTP结果页，避免旧版1800秒只读结果页继续占端口。当前有意保留新Owner，并未声称硬件已释放。

没有新增全故障矩阵、模型权重重跑或医学审核。本轮复杂实现、协议决定与实板证据验收由主代理完成，未委派核心任务；请求Sol/High，单次实际设置unknown。未推送远程仓库。
