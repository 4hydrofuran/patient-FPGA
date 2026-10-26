# 01A回交核查交接

2026-10-24 A12 CPU队友01A回交核查：REVIEWED_CHANGES_REQUIRED_TIED_OUTPUT_HEAD。446 payload/396原日志及基底/补丁hash匹配；Linux OpenMP实际6旧检查、126投影、157分类断言、60图/1308断言和ELF入口通过，1/2线程40性能样本完成。发现当前模型token_embd共享输出头漏识别，独立反例exit1；需修订，classification_accepted=false。V2旧读取器适配待A实施；本机合成图观察开销约23.4%/34.0%，不作低扰动或板速结论。未改原交付、01B/03、默认选择或旧失败；无板连接，ARM/BOARD未测。证据 `evidence/model_pl_A/20261024-cpu-peer01a-review-v1/REPORT.md`。

修订材料位于 evidence/model_pl_A/20261024-cpu-peer01a-review-v1/REPAIR_REQUEST.md 和同证据目录 tied_head_repro.cpp；原包保持只读，未自动发送。
