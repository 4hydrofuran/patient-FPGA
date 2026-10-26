# 板端基础部署交付（2026-10-26）

已通过串口和网线将现有前端交接包实际部署到KV260。板端为Ubuntu24.04.2、aarch64、Python3.12.3、Linux6.8.0-1036-xilinx；没有刷写系统、加载PL或启动真实模型。

## 位置和当前运行状态

- 根目录：`/home/ubuntu/patient-web-demo-20261026`
- 网页源码与素材：根目录下 `web_gateway/`
- 独立Python环境：根目录下 `.venv/`
- 当前网页地址：**在板上**访问 `http://127.0.0.1:8000/`。它没有开放到网线接口，电脑访问自己的127.0.0.1不是该板端服务。
- 当前模式：`DEMO_RULE`，规则回答，未接模型；`--demo-lab`未启用。
- 后台进程：本轮启动时PID3189，写在 `web-demo.pid`，已保留运行。
- 服务日志：`web-demo.log`；安装日志：`install.log`。
- 重启演示入口：`/home/ubuntu/patient-web-demo-20261026/start-demo.sh`。已在运行时无需重复执行。
- CPU入口参数模板：`start-native.sh <实际A工程目录> <新的模型日志目录>`；PL通过既有PS管理器调用 `patient_web.managed.serve_managed`，见 `BOARD_DEMO_QUICKSTART.md`。

当前网络使用电脑WLAN共享：电脑以太网192.168.137.1、板端eth0为192.168.137.2/24，网关和DNS为192.168.137.1。板端DNS解析及访问PyPI HTTPS返回200均已现场确认。采用netplan-eth0连接配置，未改其他板端网络连接；跨重启保持性本轮未单独验证。

## 本轮实际完成的工作

1. 用旧串口COM4/115200/8N1登录指定ubuntu账号，确认系统和Python。
2. 在板端建立上述新目录，通过网线传入12176821字节的软件/ARM64依赖载荷；接收摘要与本机一致。临时上传接收器成功后自动退出。
3. 使用 `venv --without-pip` 建立独立环境，再用已下载的ARM64 wheel离线安装pip与应用依赖。没有替换系统Python，没有升级系统包。
4. 安装当前 `patient-web-gateway`，`pip check`通过；FastAPI0.156.8、Starlette1.9.0、Uvicorn0.54.0、Pydantic2.14.1与本机主要版本一致。
5. 在板上启动真实HTTP网页服务，首页、脚本、样式、办公室背景和主任图片均返回200。
6. 在板上运行一次 `acceptance --single-demo`：输入“每次疼痛持续多久？”，规则回答“每次疼痛持续10分钟。”，结束后得到10/100分、持续时间分项及主任模板总结。没有运行取消、故障恢复或压力测试。
7. 在板上成功导入托管PL适配模块；这只是Python模块与依赖可用，不能据此认定PL计算接线完成。
8. 重新启用电脑WLAN到以太网的共享，补齐板端地址、网关与DNS，实测HTTPS成功。

## 证据及边界

本机保留从板上回读的 `acceptance/board-basic-20261026.json`，包含部署回执、原始HTTP一问一评结果及ARM64依赖版本。

板端也保存 `deployment.json`、`board-demo-acceptance.json`、`requirements-board.txt`。安装的原程序ZIP摘要为 `be3028ce6f45f825c9209f448faae3c083c4f06ad8b045be98e4c49e975b860e`；传输载荷摘要为 `7dc18ccb06f49a681daaabcc0e66d01935e40433b31f57d113dc5978e5414316`。

**本轮通过的是板端网页基础环境与规则模式的一问一评。真实模型、PL计算、实体显示屏与触摸仍未验证。** 后续接屏后打开上述板上地址，再接入PS已跑通的实际模型入口。当前没有添加开机自启动，也没有改动旧PS工程目录。
