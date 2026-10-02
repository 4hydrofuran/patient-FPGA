# C0 本地工程交付入口

执行目录：C:\vivado\KV260\workspaces\C。旧patient-qwen和执行包保持只读；本目录是独立C工作副本，尚未接入A管理的Git仓库。没有创建A/B目录或修改公共contracts。

病例与量表均为0.1.0-draft、DRAFT，审核人/批准依据为null。JSON Schema锁定这个状态；不能把字段改成APPROVED就放行。正式医学审核后需要保存人类依据并设计新的审核版本流程。

先读 quality/review/C0_医学审核表.md、quality/audit/旧工程业务盘点.md、app/proposals/runtime_api_v1.C0.md，完整交接在docs/handoffs/C0.md。

## 重跑

以下在本目录PowerShell执行。Python来自桌面捆绑运行时，依赖只安装在app/.deps，无全局升级。

```powershell
$taskPy = 'C:\Users\quq\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPy quality/tools/verify_c0.py
& $taskPy -m unittest discover -s app/tests -v
& $taskPy app/c0_domain.py
```

如依赖目录不存在，可在开发环境按 app/requirements-c0.lock.txt 安装到app/.deps。当前依赖为Windows CPython3.12，尚未验证Linux/aarch64；不是C2板端离线依赖包。

## 当前实现边界

SessionStore展示独立session、精确原句span/时间/意图/置信度、量表映射、可重复规则评分、missing/needs_review、问到再披露、考核不提示、结束报告和删除会话。仅进程内PC工程证明，非持久化/重启恢复实现，无访问控制HTTP服务。

C0意图来自受信任的工程测试标注，不是自动意图识别。**禁止把学生JSON或LLM输出直接转为IntentMatch**。评分方法不接受LLM指定分数/伪造引句，但不会自动证明人工标注语义正确；这需要教师标注与C1/C3实现和评测。

原句/证据存储在会话状态用于评分，普通日志只显示测试名字、状态和hash。实际语音默认不采集、不上传。C0示例输入全部虚构。没有ASR/TTS、模型调用、真实PL计数或板端验收。

教学提示只给遗漏量表标签；考核过程中不给遗漏提示。score是可信后台函数，考核报告只能在结束后展示，未来HTTP接口不得直接暴露该函数。未建立医疗审核、完整注入防护或生成事实检查验收。
