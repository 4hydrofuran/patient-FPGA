# 既有板端网页的 Python 接入覆盖包

仅在本轮 PL 验收通过、原任务完成释放和交接后部署到新的独立目录。这个包没有启动 Owner、加载设备或选择 CPU 回退的功能，不包含模型、位流或内核制品。不要覆盖原验收包或原网页。

现有网页位于 `/home/ubuntu/patient-web-demo-20261026`，已经有 Firefox 和 Python 3.12 虚拟环境。其 `patient_web.managed` 支持原 `NativePL`，不接受 resident 的 BoardService 当作相同接口。后者有自己的 session/submit/ack 生命周期，尚未实板验收，不在这里偷偷替换。

在保留图形显示的既有 PS 入口内，构建并取得本窗口批准的 `NativePL` 后接入：

```python
import sys
import time
sys.path.insert(0, '/actual/new-web-overlay')
from web_managed import serve

# 由现有 PS 管理器提供真实状态；许可服务线程继续运行。
serve(native_pl,
      is_ready=ps_accepting_requests,
      remaining_seconds=lambda: (owner.expires - time.monotonic_ns()) / 1e9,
      generation_timeout_s=180,
      port=8000)
# 返回后由原 PS 流程关闭 worker、恢复并完成 Owner。
```

`owner.expires` 在当前 Owner 中是 monotonic ns。回调不能写成常量 True，预算回调不能返回人为固定值。180 秒是网页单回答预算，需在新窗口内有相应剩余额度；预算不足时网页停止接受新问题，不扩大租约或自动重启。

PS 与网页需使用能导入现有 `patient_web` 的同一 Python 3.12 环境，或者在可信启动入口中加入该安装的 site-packages 和 web_gateway/src。现场确认实际路径与依赖后再绑定；不复制 Windows 环境，不在原验收运行期间改解释器。当前板测入口会停止 GDM，不可直接不加分析地当实体屏幕演示入口。原三请求窗口的许可只适用于原工作量，网页另开新窗口，不接管仍在验收的 worker。

提示词保持网页冻结的原长版本：当前普通 PL R0/warm/hit 包也是此版本。PC 工作区 checking.py 的新短 system 文本属于另一路候选，不在接入时同时替换。冻结参考、病例和评分不变。

开始现场接入后先读实际接口与状态，核对已封存 NativePL/managed.py 是否仍相同，再绑定上述三个真实对象。先完成一个“每次疼痛持续多久？”的真实 MODEL/FPGA_REAL 回执及主任评价，随后按需确认实体 Firefox、屏幕与触摸。不重复已通过的规则演示或增加压力、故障矩阵。

本地检查：

```text
python3 -B -m unittest discover -s bench/qwen35/web -p 'test_*.py' -v
python platform/qwen35/web/prepare.py --output <新的本地目录>
```

测试使用实际 NativePL 类、已接收 CorrelatedPL 类和明确的替身 worker，验证关联、状态、预算和所有权边界。它不执行真实模型，不是 BOARD 通过记录。

手动 HDMI 一问一评入口为 `interactive_entry.py` / `interactive_case.py`。已部署窗口、实际分配/预热证据、图形模式容量判定及临时计算设备席位规则见 `docs/handoffs/A_FRONTEND_MANUAL_LIVE_READY_20261026.md`。该入口保留桌面，先完成真实70-token缓存预热，再等待用户的一次输入；窗口和结果服务均有明确限时。它不是跨重启常驻服务，手动问题未发送前不能标为问答BOARD通过。

最新图形首问修复及实际通过记录见 `docs/handoffs/A_FRONTEND_GRAPHICAL_VERIFIED_AND_USER_READY_20261026.md`。可信宿主 `web-config.json` 可指定 `maximum_questions=2, verify_first=true`：同一已拥有worker先完成一次实体GUI验证，再创建空白用户会话，预热与权重继续复用。默认仍为一问，不增公共HTTP参数；原总提交预算不扩大。

用户授权的连续模式使用 `continuous=true`，保留原NativePL/Session流程，取消单问及finish后停模行为；`continuous_sessions.py`归档已结束场次以支持继续新建，`verify_continuous.py`验证同场多问及新场。新交互窗口60000提交/4小时的独立配置与当前活动交接见 `docs/handoffs/A_FRONTEND_CONTINUOUS_SERVICE_20261026.md`；旧单问/验收模式的默认行为和预算不变。停止整个连续服务须由可信宿主写覆盖目录的stop-request.json，正常释放后才可关机。
