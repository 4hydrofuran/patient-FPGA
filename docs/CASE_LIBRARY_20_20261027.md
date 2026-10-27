# 20例胸痛问诊扩展病例库（2026-10-27）

本次交付病例内容，不更改应用、模型或FPGA运行程序。总计20例：原有3例原文件保留，新增17例原创合成病例，待教师审阅。

- [完整病例总表](../data/patient_cases/chest_pain_20_20261027_v1/病例库总表.md)
- [数据包说明与接入事项](../data/patient_cases/chest_pain_20_20261027_v1/README.md)
- [合并JSON](../data/patient_cases/chest_pain_20_20261027_v1/case_library.json)
- [独立病例目录](../data/patient_cases/chest_pain_20_20261027_v1/cases/)
- [下载ZIP](../release/a12_case_library_20_20261027_v1.zip)

包含60句主诉备选、220条单事实及1100条双事实预编写回答，以及400条病例—问题记录（20种不同题面）。单项回答中位9字符、最长15字符；双项最长28字符。字符数不等于token数，实际Qwen分词和decode耗时尚未测量。

回答文件是AUTHORED_CANDIDATE，不是已生成并核验的MODEL_CACHE。接入时需扩展病例清单与缓存容量，并补充已知药物史等少量表达支持；尚未部署或执行模型。本地表达规则核对1211条通过，另109条均标注需新增表达支持。

参考Synthea、AgentClinic的组织方式和NHS胸痛症状维度；新增内容不复制其病例。来源、数量和检查结果见包内sources.json、VALIDATION.json与SHA256.json。
