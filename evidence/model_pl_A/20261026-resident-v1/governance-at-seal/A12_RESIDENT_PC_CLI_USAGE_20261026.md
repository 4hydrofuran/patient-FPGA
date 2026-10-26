# A12 resident PC JSON-lines CLI

此入口仅用于 Linux/WSL **x86_64 PC、software_test**。服务端负责构建身份、配额、病例与状态检查；CLI 不提供板端适配器，不连接板卡或网络。它不代表真实语音播放、医学审核或 BOARD 验收。

从仓库根目录运行，路径替换为已有 PC 服务构建和服务运行目录：

```sh
python platform/qwen35/a12/resident_cli.py \
  --build /absolute/path/SERVICE_BUILD.json \
  --directory /absolute/path/run-directory \
  --cap 72 --ack-printed-text
```

`--cap` 仅接受 `1`、`72`，默认 `72`。服务实际 `start()` 返回 `type=ready` 后才输出 ready。stdin/stdout 均为逐行 JSON；诊断写 stderr。每行输入最多 8192 字节（含换行），最多 64 行宿主命令，包括被拒绝的行；服务端另行执行其 24 次输入等权威策略限制。多余键、重复键、非对象、未知操作及非法参数会被拒绝。

可输入以下四种操作（mode 默认为 `training`，也可为 `exam`；timeout_s 默认为 30，必须为正有限数，服务可进一步限制）：

```json
{"op":"open_session","case_id":"SYN_CP_01","mode":"training"}
{"op":"submit","transcript":{"request_id":"input1","text":"疼痛在什么位置？","source":"typed","final":true},"timeout_s":30}
{"op":"cancel"}
{"op":"close"}
```

上述为各操作示例；按需要输入，等待每次结果。`transcript` 必须为原始 Transcript JSON 对象，保留宿主提供的 request_id；CLI 不生成或改写 ID，final/source/confidence 等由服务核心校验。只使用合成病例资料。正常退出须发送 `close` 并收到 `type=closed`；EOF 不等同于正常关闭。

`--ack-printed-text` 是宿主显式选择的 **PC_TEXT_TEST_ACK**：仅在 submit 返回 `type=validated_answer` 且 `tts_ready=true`，完整 JSON 已写入并 flush stdout 后，宿主才调用服务 `acknowledge(request_id, epoch)`，并另输出带 `kind=PC_TEXT_TEST_ACK`、`audio_played=false` 的 `delivery_ack`。这仅确认 PC 文本写入，不确认读者收到文本或真实音频播放。未指定此参数时不自动确认；stdin 不接受 acknowledge/ack 操作。

服务错误或确认失败即停止，不自动重试或重置。断管、Ctrl+C、异常 EOF 仅请求 cancel 并以非零状态退出，不调用正常 close，不杀进程、不重置或释放未知状态的 worker。输出固定安全错误信息，不输出异常 traceback。

此文件为使用说明；验证及结果由主任务单独执行和记录。
