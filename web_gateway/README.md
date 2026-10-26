# KV260 文字问诊前端与本地服务

面向7寸1024×600横屏的模拟问诊界面，包含文字提问、患者回答记录、状态事件，以及结束后的主任评价。页面与Python服务由同一本机地址提供，静态素材不依赖外部CDN。

当前页面采用纸质评阅记录风格，主任评价包含得分、话题覆盖、原始提问依据和待复核项。问诊阶段目前为文字交互控件；患者场景合成和语音仍待接入。

## 当前状态

- 本机规则预览可用。
- 2026-10-26已在KV260 Ubuntu24.04/ARM64/Python3.12上安装本包，页面和素材可读取，一次规则问诊及10分主任评价通过。
- A12托管PL接入口已准备；默认生成预算180秒，可配置为1–600秒。
- 2026-10-27实板通过 FPGA → CPU → FPGA 连续真实模型问答及主任评价，模式切换控件已同步。随后按用户要求关机；串口确认 Power down。详见[本轮板端流程](docs/BOARD_MODES_20261027.md)和[切换接口](docs/MODE_SWITCH.md)。
- 本轮检查了本机1024×600布局，没有重新验收实体显示屏和触摸。
- [Ubuntu桌面入口](desktop-preview/README.md)仅在本机准备和检查启动参数，未上传板子。
- 病例为合成病例，评分是待教师审核的话题覆盖草案。

## Windows 本机预览

在仓库根目录执行（需要Python3.12或以上）：

```powershell
cd web_gateway
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m patient_web --backend demo --port 8000
```

浏览器打开 http://127.0.0.1:8000/ 。选择病例1，点开始问诊，输入“每次疼痛持续多久？”，结束后查看主任评价。

`demo`明确使用规则句，没有调用模型。页面会显示“规则演示 · 未接入模型”。

## Ubuntu / KV260 运行

```bash
cd web_gateway
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m patient_web --backend demo --port 8000
```

板上浏览器访问板子自己的127.0.0.1。不要把Windows虚拟环境复制到ARM64；依赖需要在目标环境安装或使用对应架构的离线wheel。

当前服务只监听本机回环，适合板上浏览器和HDMI触摸屏。没有提供自动刷写、开机自启动或设备资源接管脚本。

## 模型接入

原CPU封存入口：

```bash
python -m patient_web --backend native \
  --project-root /actual/A-project \
  --output /actual/new-model-log \
  --generation-timeout 180 --port 8000
```

需要完整且匹配的A侧模型资产、原生程序和manifest；本目录不包含这些资产。

A12 PL入口由现有PS管理器传入已托管的BOARD NativePL及真实就绪回调：

```python
from patient_web.managed import serve_managed
serve_managed(native_pl, is_ready=ps_owner_ready, generation_timeout_s=180, port=8000)
```

网页不创建或关闭XRT进程。PS继续负责许可、健康和资源生命周期。产品启动入口需要保留图形显示，不能直接照搬会停止GDM的板测脚本。详见[单次板端演示接线](docs/BOARD_DEMO_QUICKSTART.md)和[模型负责人说明](docs/MODEL_HANDOFF.md)。

## 只做一问一评

在没有开放问诊的规则服务上执行，输出文件名必须是新的：

```bash
python -m patient_web.acceptance --base-url http://127.0.0.1:8000 \
  --expected-backend demo --single-demo --timeout 240 \
  --output /actual/new-demo-result.json
```

CPU接法使用`--expected-backend native`，托管PL使用`managed-pl`。单次模式不执行取消、故障注入、重复请求或重启。模板回退不算真实模型演示通过。

## 目录和文档

| 路径 | 内容 |
|---|---|
| `src/patient_web/static/` | HTML、JavaScript、CSS、背景和主任立绘 |
| `src/patient_web/` | 本地HTTP/SSE服务、模型适配、交付回执及评价 |
| `src/patient_web/reference/` | 冻结A02业务参考，来源与摘要见UPSTREAM.json |
| `tests/gateway/` | 接线及业务测试，原生测试包含明确的软件替身 |
| `docs/contracts/` | 文字回执、单轮结果和主任评价Schema |

- [网页接口](docs/API.md)
- [文字交付规则](docs/TEXT_DELIVERY.md)
- [主任评价](docs/EVALUATION.md)
- [规则模式完整流程工具](docs/WORKFLOW_ACCEPTANCE.md)
- [板端基础部署记录](docs/BOARD_DEPLOYMENT_20261026.md)
- [本次仓库交付说明](docs/REPOSITORY_DELIVERY.md)

## 验证与边界

安装测试依赖可用 `python -m pip install -e '.[test]'`。本次发布仅复核正常路径，不重新运行取消/故障恢复矩阵。具体结果见`docs/PUBLISH_VERIFICATION.json`。

旧阶段的XML/JSON与截图保留为历史证据，不能把旧版本全量通过记录当作新代码的全量回归结果。当前模型/PL、触控、语音状态以上述当前状态及各报告的验证范围为准。

源码目录不保存虚拟环境、运行日志、凭据、离线依赖缓存或模型权重。随包图片为用户提供的素材，来源与摘要见`docs/ASSETS.json`。
