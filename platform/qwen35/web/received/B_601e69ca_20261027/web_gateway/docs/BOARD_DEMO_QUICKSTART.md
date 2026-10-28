# 单次上板演示：本机最小适配交接

日期：2026-10-26。目标仅为一次“文字提问 → 真实模型回答 → 主任评价”。本轮板卡未连接，后续沿用 COM4、115200、8N1。本说明与当前源码配套，不表示已经上板成功。

## 已准备的内容

1. 模型生成预算默认从20秒调整为180秒，可在1–600秒内配置。它约束完整一轮模型调用，不是输入框时限，也不是首token时限。180秒是演示起始设置，不是性能保证；必须与PS许可、worker接收期限及窗口剩余预算对齐。
2. 增加 `patient_web.managed.create_managed_app/serve_managed`，接收PS已构建的BOARD `NativePL` 实例；网页不创建第二个XRT进程，也不负责关闭、卸载、重启PS设备资源。
3. 将A12内部 `a12-N` 结果先按其实际计数和状态核对，再关联到网页的session/request ID。模型实例只供该网页的单活动回合使用，不能同时被另一条应用线程调用。
4. 回执、单轮结果及JSON Schema支持 `CPU_REFERENCE` 和 `FPGA_REAL`，页面按实际路径标记；仅有后端名称或模板回复不能作为真实模型成功。
5. 提供 `--single-demo`：只发一个持续时间问题，结束并取主任评价，不做重复请求、取消、故障注入、进程重启或压力测试。托管PL入口暂不开放取消按钮；原规则演示工具继续保留。

初次演示保留现有病例、评分、长提示词及 `facts_v4` CPU路径，不切换新短提示词，不接前缀缓存。PS `NativePL` 路径沿用其R0清理。患者立绘合成、语音、故障恢复扩展和服务自启动不在本轮。

## 两种实际接法

### A. 板上已有可用的S1 CPU工程

在板上实际A工程的Python ≥3.12环境中安装本包（ARM64依赖另行准备，不复制Windows虚拟环境）：

```bash
python -m pip install -e /actual/web_gateway
python -m patient_web --backend native \
  --project-root /actual/A-project \
  --output /actual/new-web-model-log \
  --generation-timeout 180 --port 8000
```

这条路径仍使用A09封存CPU入口、manifest和模型资产校验，页面显示CPU。`/actual/...`均替换为现场路径，日志目录必须是新的。它不启用PL；如果现场只有A12托管PL版本，采用下面的B接法，不强行替换清单。

### B. PS管理器已经运行A12 PL模型

由PS负责人在已有、允许图形界面共存的运行入口里，把已经构建好的 `NativePL` 交给网页：

```python
from patient_web.managed import serve_managed

# native_pl：PS原有管理器已经校验并托管的BOARD NativePL实例。
# ps_owner_ready：查询PS现有“允许接收应用请求”状态的函数，返回bool。
serve_managed(
    native_pl,
    is_ready=ps_owner_ready,
    generation_timeout_s=180,
    port=8000,
)
```

`native_pl`、`ps_owner_ready`是接线位置，不是新造的PS启动命令；连接后在实际运行工程中定位它们。不要用常量True代替真实管理状态。PS必须继续处理worker许可与健康观察，worker传输的读取期限也应容纳本轮预算。函数阻塞至网页服务退出，返回后仍由PS原管理流程收尾；网页退出不是worker已安全释放的证明。

现有板测脚本有停止GDM、隔离桌面的行为，不能直接当成7寸显示屏演示启动脚本。需要由PS负责人选用保留图形显示、资源预算也允许浏览器运行的入口；本包不自行删除该隔离条件或修改任何硬件管理脚本。最新资源探测包尚标为UNBOUND，不能把它的plan-only入口当产品驱动运行。

模型仅在初始化及返回的实际身份为 `FPGA_REAL` 时接入，`PC_MATH_DOUBLE` 不接受为板端模式。网页不会把CPU静默换成PL或反向回退，也不启动ASR/TTS。

## 一次演示的操作

1. 在板上浏览器打开 `http://127.0.0.1:8000/`，屏幕使用1024×600横屏。浏览器和服务都在板上运行，无需公网或上位机提供网页。
2. 选择合成病例1，开始问诊，输入“每次疼痛持续多久？”。
3. 等待完整回答及事实检查结束；预期对应病例事实为“每次疼痛持续10分钟。”。保留板端实际输出，不用固定演示句冒充模型生成。
4. 点结束问诊；应看到10/100分、持续时间已覆盖和主任模板评价。

如需自动保存一问一评的原始结果，在没有开放问诊的服务上执行：

```bash
python -m patient_web.acceptance \
  --base-url http://127.0.0.1:8000 \
  --expected-backend managed-pl \
  --single-demo --timeout 240 \
  --output /actual/new-single-demo.json
```

CPU接法把 `--expected-backend` 改为 `native`。报告等待240秒略大于网页预算180秒，便于接收最终结果；该参数不会延长PS硬件窗口。输出父目录须已存在，文件须是新的。

这条命令会自行创建一场问诊；不要在手动演示已经开始后运行。单次模式超时会保留活动任务交给PS负责人检查，不发送取消、强杀或重启。不要反复重发增加负载。

成功应同时包含 `answer_source=MODEL`、`model_called=true`、匹配的 `actual_backend`、正确的文字回执以及10分主任评价。模板回退只报告PARTIAL。HTTP结果证明文字交付，不证明实体触摸或浏览器已读；现场另保存一张屏幕照片或截图即可。

## 本机检查与仍需现场完成的事

本轮仅运行4项正常接线/交付检查：实际冻结NativePL Python类＋替身worker的一问一评、真实本机HTTP单次探针、原CPU适配接线、规则文字交付。没有运行取消/故障恢复/压力矩阵。原生类引用来源：仓库 `c3cdd16ad109b19c8f518623fcd5f1c0143d4b7c` 发布的 `SOURCE.zip` 内 `system_qwen35/app/native_pl.py`；测试副本SHA256为 `574a72225e252e462d46c9c4f547e158b25032c5f6fb73f3537343d0b6b626bd`，仅供协议接线测试，不含真实模型执行。

WSL Ubuntu-24.04可启动，Python3.12.3/x86_64可用，但其系统Python尚未安装本网页服务依赖。本次使用现有Windows虚拟环境完成本机验证，未更改WSL配置或安装新依赖。

接板时只剩现场相关步骤：确认系统与Python、定位已跑通的PS入口/模型资产、接入上述调用、确认图形显示共存，再完成一次真实生成和评价。若选PL，管理器普通应用路径及当前设备状态须由PS负责人确认可用，不能拿本机替身结果替代。

当前证据：`MINIMAL_ADAPTATION_VERIFICATION.json`、`minimal-adaptation-tests.xml`、`acceptance/minimal-managed-fixture.json`。原83项/64项报告属于前一版本历史，不能作为本次新源码的回归通过记录。
