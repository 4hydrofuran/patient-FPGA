# 回交包要求

建议文件名 `A12_CPU_PEER_01A_03_<日期>_v<版本>.zip`，内部只包含：

```text
README.md                  如何复现、当前完成域与未完成项
BASELINE_REF.json          原交接包manifest/zip SHA、运行时/源码基底SHA
DESIGN.md                  分类策略和拼接布局/所有权/调度设计
patches/01A.patch          分类与配套测试
patches/03.patch           拼接候选与配套测试
source/                    改动后的必要源码；说明patch应用顺序
tests/                     新目标与边界测试、执行入口
evidence/COMMANDS.json     实际命令、环境、退出码、日志路径/hash
evidence/RESULTS.json      原始重复样本、域、null/NOT_TESTED字段
evidence/FAILURES.json     所有失败、修复、最小复现与未决项
PROFILE_SCHEMA.json        新分类格式及旧字段迁移
REPORT.md                  独立01A、独立03、组合结果及限制
ROLLBACK.md                原源码/候选/配置如何还原
MANIFEST.json              回交包全部文件长度与SHA256
```

可以从 `templates/RESULTS.json` 和 `templates/FAILURES.json` 开始填，未运行项不能改为PASS。记录OS/CPU、编译器、编译选项、线程、输入shape/类型、观察开关、计时范围及源码hash。

只交源码、补丁、必要小测试数据及日志。不要交账号密码、私钥/令牌、许可证授权正文、整个WSL镜像、模型权重、SDK、PL大产物或编译缓存。既有B交付保持只读，候选单独标作者/维护者。不自动推送远程或发送给其他人。
