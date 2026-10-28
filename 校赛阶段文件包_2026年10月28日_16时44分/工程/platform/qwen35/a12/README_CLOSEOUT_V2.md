# A12 收口修复（2026-10-24）

本轮只解决单投影旧窗口的收尾：不启动模型，不装卸PL/驱动，不重启。
已通过独立板端复核及延时复核，旧manager27132已定向结束（-9，保留异常退出），旧租约原字节归档，规范双锁释放。
原始单投影计算/消费者结果、首次收口失败、A11和01—06封存件保持不变。
当前入口：`C:/Patientqwen/evidence/model_pl_A/20261024-step07-finalize-v1/REPORT.md`。

## 本次工具不能直接重放

`step07_finalize_*` 的精确执行脚本绑定boot、PID、startticks、旧清单和租约摘要，只允许无设备/子进程/XRT的已知等待进程。
信号仅发一次，使用pidfd；当前旧进程已退出，再运行应拒绝，不是通用强杀工具。
任一门槛失败时不重发信号，不删除租约，不操作硬件，只保存STOP和独立核对状态。

## 后续管理器组件

`window_closeout_v2.py` 是独立派生组件，保留 `window.py` 原件。未来的新包须显式改为：

```python
from window_closeout_v2 import Window
```

并在清单中固定该文件、`step07_finalize_policy.py`、`step07_supervisor.py`及原有依赖的摘要。
该修改不改变模型、数学、公共ABI或B核。生成器 `step07_finalize_window.py` 可复现源码；原始文件已存在时拒绝覆盖。
当前旧板包未被改写，未来完整管理器/板端生命周期仍须在新审阅窗口验证；本轮仅7项Linux PC测试通过。

v2每次完整扫描（含失败）写入 `finalization-events.jsonl`。只有已知进程/FD表短暂变化才最多重查4次；不把不完整扫描改为通过。
设备占用、未知问题、boot或内核异常立即拒绝。正常worker退出、完整FD/VMA、默认PL/GDM、旧所有权全部证明后才归档租约、关闭自己的锁描述符。

失败时保留原ISOLATED记录、锁和租约。显式恢复请求为该窗口私有证据目录中的root所有、不可组/其他用户写入的
`finalize-request-0001.json`（后续请求换新序号），严格字段如下：

```json
{
  "schema": "A12_FINALIZE_ONLY_V2",
  "op": "finish_only",
  "boot_id": "本次boot",
  "window_id": "本次新窗口",
  "manager_pid": 0,
  "manager_start_ticks": 0,
  "lease_sha256": "本次租约摘要",
  "expires_monotonic_ns": 0
}
```

示例中的0为占位符，不能提交。必须实读本次PID/startticks/租约和单调时钟，过期时间在未来30秒内。
仅允许已正常退出的worker；不终止仍运行或异常的worker，不提交计算、不复位、不恢复PL。
通过请求会先被原子改名保存，再重新跑全部收口门槛，成功后管理器自行正常退出。
不能用新组件替旧进程事后声称“正常退出”。

本轮已执行的验证命令（直接重放会因证据已存在而拒绝覆盖）：

```powershell
wsl -d KV260-A-2204 --cd /mnt/c/Patientqwen -- python3 -B platform/qwen35/a12/step07_finalize_test.py
wsl -d KV260-A-2204 --cd /mnt/c/Patientqwen -- python3 -B platform/qwen35/a12/step07_finalize_window_test.py final
```

本轮原始命令、退出码和测试收据在上述证据目录。测试包括一个仅持临时文件锁的本机等待子进程，设备计算为0。
