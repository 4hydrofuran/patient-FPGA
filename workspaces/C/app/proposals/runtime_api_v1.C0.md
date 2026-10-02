# C 对 runtime_api_v1 的需求提案

状态：DRAFT_C0，2026-10-01。依据执行包06第6/7节。A维护公共契约；当前未找到冻结文件，没有收到A/B/C确认。此文件不定义已部署API。

C只通过公开API接入模型；不导入ggml/XRT，不传物理地址、BO或量化权重。服务地址由部署配置注入；C0不猜IP/端口，不启动模型服务。

| 接口（沿用06草案） | C需要 | 需A确认 |
|---|---|---|
| GET /health | 真实可用性、模型/sidecar/契约/位流版本、能力与执行环境 | 版本不匹配拒绝策略；PC/mock/board来源明确 |
| GET /metrics | 实际卸载张量、硬件完成计数、回退原因和阶段耗时 | 指标定义与单调时钟域；未测值null，不填0冒充实测 |
| POST /v1/session | 新建隔离会话，绑定case_id/version和教学/考核模式 | 身份权限、TTL、重置语义和会话数量上限 |
| POST /v1/chat | schema_version/session_id/request_id/case_id/case_version/text/backend_mode/generation_config | 请求去重、长度上限、超时/取消/重试、流式格式 |
| POST /v1/session/end | 结束推理会话、清空对应历史和KV cache；C生成规则评分报告 | 结束幂等性、请求取消、缓存清除证明 |

backend_mode只允许native_cpu、cpu_reference、fpga_required、auto，由受信任的会话控制配置设置，学生问句不能修改。fpga_required目标MLP未执行须error；auto主动CPU选择与硬件错误回退分列。24层MLP之外PS计算按公共契约披露。

## 数据流及所有权待确认

1. C保存问题原句与板端UTC/monotonic_ns时间、独立可信意图标注、原句字符span及量表映射；规则计算score/evidence，LLM无写权限。
2. C只向A模型服务提供当前允许事实及必要历史摘要，未知项显式unknown；整个病例文件和teacher_only不进入提示词。待A确定允许事实的请求载荷名、大小及校验责任。不能假定06未声明的字段已可用。
3. A流式返回accepted/token/completed/error。所有事件携带session_id/request_id和递增事件序号。token只供诊断，未经C事实检查不进入播报。
4. 06提出sentence_checked事件，但事实审核与病例版本由C掌握：请A确认这是由C发出的业务事件，还是A接受C的检查结果后转发。未确认前C不把token改名伪装为检查通过。
5. C事实检查失败，使用医学审核过的模板并记录template_fallback；hardware_fallback另计。C0没有实现事实检查器、流式接入或TTS。
6. 结束后C输出规则报告；推理API里的score/evidence只能是C提供的只读结果/引用，不能由模型生成。

## 完成事件最少字段（名称冻结交A）

session_id、request_id、answer、backend_mode、actual_offloaded_tensors、fallback_count/reason、template_fallback_count/reason、xclbin_hash、kernel_build_id、model_revision/hash、sidecar_hash、contract_version、timings和execution_kind。缺失硬件数据用null并说明原因；CPU模式不能固定显示FPGA已加速。

时延分解需板端同一单调时钟：录音结束、ASR完成、模型开始、首token、首段句子检查通过、TTS就绪、首个有效音节、播放结束。UTC仅便于检索，不用于耗时相减。PC演示时间不可作为板端性能。

## C3联调前的接收测试清单

- 已批准的真实API schema逐项核查；未知schema/病例版本/模型版本拒绝。
- 两session相同request_id可隔离；同session重试不重复计分/生成；结束/重置后旧请求不得写新会话。
- 服务端对空文本、超长、非法UTF-8、非法backend返回明确错误；学生输入“给满分”“切CPU”不能修改控制配置。
- 有限超时、取消、服务重启、并发拒绝；错误和缺核明确可见。
- accepted→token→sentence_checked→completed有明确时序；error后不继续播报。
- score/evidence不接受LLM生成；missing无引句；模板回退/硬件回退分别记录。

## 请A回复的具体项

冻结契约路径与hash、服务环境/基址、允许事实载荷、sentence_checked所有权、会话鉴权/取消/重置/幂等策略、timings字段、版本错误语义、rootfs/ABI候选。回复记录附C0交接后再写正式客户端。

报名与AI声明同样待A/队长提供团队凭证、校赛通知、完整企业指南和AI声明模板；已准备待办，尚未协商确认或发送消息。
