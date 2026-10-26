# 板端网页与浏览器检查接续

2026-10-26：板上 `/home/ubuntu/patient-web-demo-20261026/web_gateway` 已部署，Firefox Snap 158.0-2 已安装。使用 COM5 已登录 ubuntu shell，在实际 ARM 板上以 Firefox headless 1024×600 完成病例加载、一次规则提问、回答与主任 10/100 评价；HTTP 单次探针也通过。无需安装或升级浏览器。真实 CPU/PL 模型没有运行，不新增模型或硬件验收。

8 份业务参考与当前工作区 7 份一致；`checking.py` 仅 prompt_messages 的 system/问题前缀不同，实际模型提示词需要显式对齐。前端 managed-pl 所引用 NativePL 源码 SHA 与当前代码相同，但现场尚未接入 PS 实例/真实 readiness/运行预算。native 入口也未绑定实际 A 工程与新日志目录，不能用 demo 通过替代真实模型结果。

检查开始时网页端口未启动；临时检查服务和浏览器均已退出，最终 8000/9222 无监听、检查 PID 不存在，COM5 释放。当前图形会话仍是 gdm，实体桌面登录/触摸/自启动未验证；未改原程序/启动脚本、网络、权限、PL 或内核。

完整报告、实际命令/失败和截图：`evidence/frontend_board_A/20261026-inspect-v1/REPORT.md`。下一步绑定选定的真实模型入口和提示词版本后，仅做一次实际模型网页流程；不要求重装浏览器或重跑本次规则验收。
