# 20例胸痛问诊病例库

最新：2026-10-30 v2，补充教师端疾病关联与来源说明。

- [疾病关联与现实来源说明](../data/patient_cases/chest_pain_20_20261030_v2/疾病关联与来源说明.md)
- [完整病例总表](../data/patient_cases/chest_pain_20_20261030_v2/病例库总表.md)
- [结构化疾病关联](../data/patient_cases/chest_pain_20_20261030_v2/diagnostic_annotations.json)
- [合并JSON](../data/patient_cases/chest_pain_20_20261030_v2/case_library.json)
- [使用说明](../data/patient_cases/chest_pain_20_20261030_v2/README.md)
- [v2完整ZIP](../release/a12_case_library_20_20261030_v2.zip)
- [原始v1内容包](../data/patient_cases/chest_pain_20_20261027_v1/README.md)

20例均为合成场景，没有记录到一一对应的真实患者原型。医学关联是依据现有症状和公开参考作的教学性推断，所有confirmed_diagnosis均为null。每例提供候选疾病、现有支持事实、判断限度、需要补充的信息和引用。

患者的11类事实、60句主诉、1320条回答候选及问题集保持不变。新增标注只供教师备课，不进入患者提示词，也不作为唯一诊断评分答案。现有短答长度不变；未运行模型或板卡，未改运行程序。
