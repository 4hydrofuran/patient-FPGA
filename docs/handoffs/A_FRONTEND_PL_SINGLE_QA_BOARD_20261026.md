# 板端网页真实 PL 单问单评完成

2026-10-26：**PASS_BOARD_FRONTEND_PL_SINGLE_QA**。用户确认PL验收已完成且本任务优先后，已部署到 `/var/lib/kv260-a12/web-20261026-v1`，复用原网页及已通过模型/硬件。

板上Firefox158.0 headless 1024×600实际提问“每次疼痛持续多久？”，真实MODEL/FPGA_REAL回答“每次疼痛持续 10 分钟。”，页面约68.361秒显示，主任原规则评价10/100。仅1次真实模型生成、72次权重加载、1656次许可/后端对应完成；没有Vivado/Vitis、重启、刷写、整套重复验收、语音或压力测试。

本次网页/浏览器/模型均已退出，默认PL/GDM恢复，active lease=false、ZOCL=false，板仍上电、COM5释放。Firefox和worker exit0；管理器正常终态/PID消失已读回，但detached父进程未waitpid，manager_exit_code=null，不补造。等待自动跟进pl已删除。

原长提示词/病例/评分/公共ABI不变，未接短提示词resident候选。接口源码为 `system_qwen35/app/web_managed.py`、`platform/qwen35/web/board_case.py` 和 `board_entry.py`；PC10项通过。一次性目录已消费，不能原目录重放；常驻服务、实体屏幕/触摸和语音未验收。

完整报告与原件：`evidence/frontend_board_A/20261026-board-integration-v1/REPORT.md`，结果 `RESULT.json`，三张截图及运行回执在其 `board-receipt/bundle/run-v1/s2/`。ZIP SHA256 `7eb4fc83a57f05f922f17206b5a8fe3f669577a9cc31fea747f82d30274cc9d7`。
