# A02 病例约束、评分与软件测试

状态：合成草案，待教师审核；不是诊疗工具，也不是正式考核系统。只允许明确的`software_test=True`会话。
本目录由A维护；不修改旧`originalpatienqwen/`或C的`app/`、`cases/`。

## 已实现

| 模块 | 责任 |
|---|---|
| cases/schema.json及SYN_CP_01/02/03.json | 三份无真人来源、无诊断标签的胸痛事实草案 |
| app/domain.py | 严格病例/转录校验，只读白名单路径，未知与否定分开 |
| app/planning.py | 明确同义规则、上下文路由、AnswerPlan，最多两个主题，不调用LLM抽意图 |
| app/checking.py | 数值/单位/肯否/关系及必答事实的整句有限语法；不可解析记uncertain |
| app/scoring.py | 原句、字符span、原始时间、否定和槽位证据；确定性话题覆盖分，不评人格/真实情绪 |
| app/session.py | 接收、验证、待交付、确认历史分离；幂等、取消epoch、训练/考核反馈隔离 |
| app/native.py | 复用A01固定Qwen3.5 CPU进程，4线程/1024容量/非思考/R0全清理；无GPU/视觉/MTP |
| app/cli.py | 本地JSONL演示入口，学生输出不包含病例、量表、原始候选；非生产服务 |

所有Case/unknown-policy/rubric均为草案。未知事实只能用明确“不清楚”语义；仅当本轮只有一个未知事实时才接受裸“不清楚”。缺失事实不变成否定。输入只能带最终转录字段，不能指定病例路径、修改量表或配置。

AnswerPlan保留intent、allowed、required、unknown策略、已确认披露和相关历史。模型只收到当轮许可事实和原问题；系统评分不调用LLM。模型的一整轮完整候选先通过检查才设置`tts_ready`，失败保留candidate/原因并明确TEMPLATE；实际超时为TIMEOUT；损坏/隔离后端返回error且无可播文本。检查器不是开放领域医学语义判定器。

## 运行

Windows已有Python可运行规则单测：

```powershell
platform/local/a1/venv/Scripts/python.exe -X utf8 -m unittest system_qwen35.app.test_a02 -v
```

在现有WSL `KV260-A-2204` 中，从`/mnt/c/Patientqwen`运行（output必须是新目录）：

```bash
python3 -m system_qwen35.app.cli --case SYN_CP_01 --mode exam --software-test --output eval/qwen35/a02/manual-new
```

每行输入一条JSON，EOF结束；只输入合成问题，不输入真实患者或学生隐私：

```json
{"request_id":"q1","text":"哪里痛？","source":"typed","final":true}
```

原始合成审计与话题覆盖评分存于本次输出目录。终端输出后记`PC_TEXT_TEST_ACK`，**不是音频播放确认**。当前同步调用期间拒绝并发状态修改；即时打断生成/实际声卡播放由A03接入。真实超时使用SIGUSR1后隔离进程，需关闭并显式重启，不自动静默回退到另一后端。

## 测试与审核

证据：`eval/qwen35/a02/`，实际命令和退出码：`platform/qwen35/a02/evidence/`。
开发集24题；DEV-010原标签错误已显式保留v1并修订v2。300项heldout是独立编写计划，目前0条已编写/审核，不用于调参。
教师表为`teacher_review.csv`；逐项审核病例值、未知策略、量表、表达语法、开发gold和独立最终集，填写真实姓名/日期/意见。代码没有“自动审核通过”路径；获批后应通过新的版本变更和回归发布。

话题选择仅参考[NICE CG95的病史采集条目](https://www.nice.org.uk/guidance/CG95/chapter/recommendations)；该依据不验证本项目病例取值、诊断或评分。详细用途限制见`eval/qwen35/a02/governance.json`。

无ASR/TTS录音、无板端执行、无功耗测量。PC输出和资源耗时不代表KV260性能。
