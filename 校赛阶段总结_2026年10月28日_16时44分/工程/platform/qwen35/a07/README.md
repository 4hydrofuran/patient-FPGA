# 不等待 B 实物的 A07 准备入口

所有命令从仓库 `/mnt/c/Patientqwen` 执行。沿用 `KV260-A-2204`、2026.1 Common SDK；不安装工具，不替换 A05 的源码或 x86 库。

```bash
python3 platform/ra02/build_queue.py submit --owner A --label a07-new-a53 -- /bin/bash /mnt/c/Patientqwen/platform/qwen35/a07/build_a53.sh
python3 platform/ra02/build_queue.py run-next
python3 platform/ra02/build_queue.py submit --owner A --label a07-new-host -- /bin/bash /mnt/c/Patientqwen/platform/qwen35/a07/build_host.sh
python3 platform/ra02/build_queue.py run-next
python3 platform/qwen35/a07/test_delivery.py
```

每次队列生成独立工作目录。失败 active marker 须检查实际进程/结果后人工归档，不能自动跳过。`audit_build.py` 是本次收口证据收集器，绑定本次命令 receipt；新一轮应指定新的 receipt/输出，而非覆盖已封存数据。

CPU 构建明确 `GGML_NATIVE=OFF`、`GGML_CPU_ARM_ARCH=armv8-a`、`-mcpu=cortex-a53`，不启用 dotprod/i8mm/SVE/KleidiAI。全部动态库使用可搬移的 `$ORIGIN`，新可执行文件默认项目根 `/opt/patient-qwen`；未在板端创建该目录，非安装包。

实际 B ZIP 到达后可先只读检查（不会解压、执行或认定接收通过）：

```bash
python3 platform/qwen35/a07/inspect_delivery.py /absolute/B-supplement.zip --sha256 <B公布的实际hash> --out /new/path/archive-inventory.json
```

输出逐文件 SHA256 和 XO 内 XML；拒绝路径穿越、大小写重复、符号链接、Windows保留名、加密、超量解压及 XML DTD。README 写了 XO 路径而没含实物会得到 missing_actual_xo=true。`accepted/frozen` 永远 false，A06 数值/同版本/仿真验收另做。

部署准备风险：现有 Common rootfs/SDK 库一致性不等于 KV260 已有可启动配套；EDF/Kria BOOT/DT 与 Common PetaLinux 不可拼接。保留 `platform/a1/common_image_candidate.json` 和 RA02 启动/恢复检查单中的阻断。禁止本工具写SD/QSPI或宣称4GB可分配。
