# CPU / FPGA 推理模式切换

日期：2026-10-27。目标仍为 1024×600 横屏触控。

页面病例栏新增“推理”下拉框。回答生成时禁用；一轮完成后可切换，继续使用同一病例和对话。切换期间显示加载状态。历史回答保留各自的实际 CPU / FPGA 来源，不随当前选择更名。结束问诊仍调用同一套主任评价。

服务只显示启动时明确配置的选项。原有单模式启动继续使用；它不会凭空显示一个尚未配置的模型。

接口：

```http
POST /ui/v1/backend
Content-Type: application/json

{"request_id":"switch-1","backend":"native"}
```

`native` 是 CPU；`managed-pl` 是 PS 托管的 FPGA。202 表示已接受，随后 GET `/ui/v1/status`，待 `ready=true` 再提问。`backend_options` 列出选项；`backend.execution_kind` 是当前模型的实际执行类型。执行中返回 BUSY，前端相应禁用控件。切换失败明确显示失败，不自动改用其他模式。

CPU 使用板上既有 bundle 中的 `bin/qwen35-a12`，以 `all / TILED / 2线程 / ubatch8` 启动，去除子进程的 `SP_A12*` 路由配置，使其运行 CPU_REFERENCE。沿用同一 GGUF、sidecar、聊天模板和事实检查，单次输出上限24 tokens。未生成 CPU 版本的硬件驱动。

PS 接入位置是其现有 `web_managed.create_app()` 返回前：

```python
from pathlib import Path
import uuid
from patient_web.stdio_cpu import BoardCPUEngine

# app 已由已有 NativePL 和 PS 健康/剩余时间回调创建。
coordinator = app.state.coordinator
coordinator.backend_options = {
    "managed-pl": {"label": "FPGA", "factory": coordinator.factory},
    "native": {"label": "CPU", "factory": lambda: BoardCPUEngine(
        bundle, Path(cpu_log_root) / uuid.uuid4().hex)},
}
```

FPGA 切出时仅解除网页包装对象；原 PS owner 继续持有和管理 FPGA worker、许可及运行窗口。CPU worker 按需创建，切出后发送正常 shutdown。切回 FPGA 使用原来的已预热 worker。网页没有接管硬件装卸。

本次同步文件：`manager.py`、`api.py`、`managed.py`、`stdio_cpu.py`、`static/index.html`、`static/console.js`、`static/evaluation.css`。板端在新的 `web-modes-20261027-v2` 目录集成，之前 `web-multi-20261026-v1` 保留。首次重启后临时锁文件缺失、GDM占用加速器的问题及最终验证结果另见本轮板端记录。

`desktop-preview/` 是独立的 Ubuntu 桌面入口准备目录，本轮不上传。它只打开既有服务窗口，不负责启动 PS 模型。
