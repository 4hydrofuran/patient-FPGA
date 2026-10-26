# 前端更新仓库交付

日期：2026-10-27。目录仍为web_gateway/，更新原前端分支frontend/web-gateway-20261026，仅修改该目录。

本轮交付CPU/FPGA切换接口、触屏选择控件、CPU程序适配器、板端启动脚本、已验收PS接入层源码和说明。板上已走通FPGA→CPU→FPGA三次真实模型问答及主任评价；随后按用户要求正常收尾并关机。

desktop-preview/提供Ubuntu桌面入口的本机预备文件。本轮没有上板安装，Ubuntu图形启动仍未验证。mode-switch-preview.png是本机规则控件演示，不能当作实板模型画面。

不包含虚拟环境、runtime缓存、凭据、个人工作区交接历史、模型权重、离线依赖、原生二进制或硬件镜像。旧阶段报告保留，不能作为当前代码的全量回归结论。当前验收见BOARD_MODES_20261027.md、BACKEND_MODES_VERIFICATION.json及acceptance/backend-modes-board-20261027.json。

SOURCE_MANIFEST.json记录本次提交索引中的文件SHA256，排除清单自身。PS模板仅是接入层，依赖已有完整PS bundle和模型部署，不承诺在全新Ubuntu上独立启动FPGA。
