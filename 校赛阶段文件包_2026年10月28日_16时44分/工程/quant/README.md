# A2 格式无关准备，版本 a2-preparation-0.1

当前只实现源权重/图映射、真实未量化激活采集、浮点方向复算、A3 logits对比工具和内存规划。`quant_v1`仍为draft.2，**没有sidecar、没有W4A8 CPU内核、没有B独立交叉验收，不是A2通过**。不改冻结状态，不把GGUF Q4_K_M字节解释为自定义格式。

## 可复现入口

从 `C:\Patientqwen` 运行，Python使用现有 `platform/local/a1/venv/Scripts/python.exe`。只有源码审计脚本不依赖NumPy/PyTorch，也可在WSL的python3执行。每次输出路径必须全新，不覆盖已有证据。

```text
python quant/model_audit.py --out quant/evidence/source-graph-audit-NEW.json
python quant/capture_float_inputs.py --out platform/local/a2-float-capture-NEW --report quant/evidence/float-capture-NEW.json --threads 4
python quant/validate_float_capture.py --capture platform/local/a2-float-capture-NEW --audit quant/evidence/source-graph-audit-NEW.json --out quant/evidence/float-orientation-NEW.json
python -m unittest discover -s quant/tests -v
```

真实已执行命令记录在 `quant/evidence/*run-20260928.json`，不是上述NEW占位命令。本次使用torch2.13.0+cpu、transformers4.57.6、numpy2.5.1，线程4、interop1、CPU FP32、eager attention、use_cache=false。模型config标注的transformers4.43.1是训练/发布元信息，不伪称本次使用该运行版本。没有下载/安装新依赖、联网加载模型或执行remote code。

## 源与图语义

官方BF16 safetensors SHA已重新校验；按真实config解析24层、hidden896、intermediate4864、vocab151936、14个attention heads/2个KV heads、SiLU。72个MLP张量逐个记录shape、dtype、offset、原始字节hash；固定llama.cpp的关键源码逐文件与已固定归档核对，而非仅相信目录名。

| HF原始权重 | 逻辑 W[N,K] | GGML ne[0:2] | 图输入 → 输出回调 |
| --- | --- | --- | --- |
| layers.i.mlp.gate_proj.weight | [4864,896] | [896,4864] | ffn_norm → ffn_gate |
| layers.i.mlp.up_proj.weight | [4864,896] | [896,4864] | ffn_norm → ffn_up |
| layers.i.mlp.down_proj.weight | [896,4864] | [4864,896] | ffn_swiglu → ffn_out |

依据：固定converter的Qwen2分支调用父类原样返回张量，tensor_mapping给出ffn名称，GGUF writer反向序列化维度，模型loader声明ne，图执行 `ggml_mul_mat(weight,input)`。因此源行主序的最后一维K连续，逻辑运算是 X·Wᵀ，**不是对payload再转置一次**。完整路径/hash/行号见审计JSON。LoRA未启用；将来启用adapter需重新审计。

Qwen2的无bias分支不保证出现名为ffn_down的回调，本版最终线性输出用ffn_out定位。最后一层可能只保留请求输出的token，A3不得假定所有层总有256行。

源MLP没有bias；72个attention Q/K/V bias保留在PS。LM head没有独立权重/偏置，config的tie_word_embeddings=true；源embedding只计一份。llama.cpp缺output时采用TOKEN_EMBD的TENSOR_DUPLICATED张量，实际buffer是否复制依赖backend/加载策略，不能从源共享关系推导“零额外内存”。本次HF采集验证输入/输出embedding的data_ptr一致。

## 真实激活交付范围

`platform/local/a2-float-capture-20260928/manifest.json` 列出第0、11、23层的9组样例，每组input/output都是小端FP32、T=8，取固定256-token提示的第248..255号位置。gate/up的input为[8,896]，down的input为[8,4864]。每份文件有shape、字节数及hash；B可以取前T行形成T=1..8的线性算子输入，不能宣称那是单独执行短上下文的模型激活。

这来自原始BF16权重转FP32后的HF原模型计算，不是llama.cpp/F16图采集，也不是量化传播后的激活。逐个原始权重slice重新执行FP32 linear，9组误差均为0；三层gate/up输入逐字节一致，SiLU(gate)×up与down输入最大误差均为0。仅证明本次数据/方向/拓扑一致，不证明W4A8或硬件正确。

## A3 logits对比接口

观察目录含 `manifest.json` 和小端FP32二维logits文件[位置数,vocab]。复用本次manifest的schema `a2-float-observation-0.1`，固定源revision/hash、prompt/template/token hash、**实际teacher-forced context_token_ids**和positions；位置p保存处理token[p]后的next-token logits。不能比较各自自由生成导致上下文分叉的logits。

```text
python quant/compare_logits.py ORIGINAL_DIR SIDECAR_CPU_DIR --kind quantization --out NEW_QUALITY.json
python quant/compare_logits.py SIDECAR_CPU_DIR SIDECAR_FPGA_DIR --kind hardware --out NEW_HARDWARE.json
```

量化质量：stage必须original→sidecar_cpu。硬件误差：stage必须sidecar_cpu→sidecar_fpga，sidecar_sha256必须相同。两者还必须有一致的 `comparison_basis.engine_commit`、`comparison_basis.non_mlp_model_sha256`、`comparison_basis.evaluation_protocol`（应固定精度/attention/KV等计算设置）；A3接入后提供这些实证字段，不能为了通过检查随便填。

本次HF观察没有A3 comparison_basis，故只能用于 `--kind diagnostic` 的工具自检，不能直接和llama.cpp比较后把引擎差异叫量化误差。输出max absolute、RMSE、cosine、KL(reference||candidate)、top1一致率，不自动设置阈值或判验收通过。相同观察自检误差0只是工具自检。医学/病例质量属于C，当前固定提示是非医学smoke，不作质量结论。

模型质量检查、冻结向量整数bit-exact检查和硬件浮点误差是三种不同证据；本工具不代替后两者。A2不实现新的全图推理运行时。

## 2026-10-01 职责接续说明

RA01 起，生产 sidecar 导出器及资产 manifest 由 C 在 `quant/exporter/` 维护；这里既有模型审计/浮点采集/比较器由 A 保留。旧文中的 A2 未完成项为历史状态，不再代表生产导出器归 A。B 负责独立 golden，A 保留激活量化、S1 CPU 和图消费。当前契约仍未冻结，详见 `docs/handoffs/A_TO_BC_20261001.md`。
