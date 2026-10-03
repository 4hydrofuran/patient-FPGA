# B → A：B03 / A06 一次性补交包

日期：2026-10-03。针对 A 的 B_MISSING_AND_DEFECTS.md（旧提交 fdd1d65），补齐当前 double 候选的实际文件和独立回放证据。B03_REPORT.md 是最初紧凑包的开发报告，其中“排除 TV/向量”的描述不适用于本补交包；本文件与包根 B03_supplement_manifest.json 说明新增内容。

## GitHub 实际文件下载

- [完整补交 ZIP：B03_A06_supplement_20261003.zip](https://github.com/4hydrofuran/patient-FPGA/releases/download/b03-a06-supplement-20261003/B03_A06_supplement_20261003.zip)
- [Release：校验文件、中文说明及验收收据](https://github.com/4hydrofuran/patient-FPGA/releases/tag/b03-a06-supplement-20261003)
- ZIP 大小 137,874,097 字节；SHA256：`506f079daabf37f6dc539d35c49add0b4c0e7629a0a97c461c470b0f75c59513`。

2026-10-03 已完整下载四个远端附件，逐文件大小和 SHA256 与本地原件一致。远端 ZIP 与此前 B03_A06_补交包.zip 字节一致，下载文件名采用 ASCII。本次补齐此前未发布的实际二进制附件；A 独立接收复测仍由 A 确认。

**须把实际 ZIP 交给 A。只克隆 Git 或提供本机路径，不等于已接收 XO 与原始向量。** 本包不代 A 签收；A 独立复测后才能更新其 NOT_ACCEPTED。

## 唯一候选

double，build_id 0xB3030002，私有 meta 40 字节。

实际 XO：artifact/b03_candidate/w4a8_linear_v1.xo，19,596,752 字节。SHA256：96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23。

源 SHA256：7e1eb3450c0839254148c5fecebf4be1b2d76ca7c18f39e8df8e63769d5874d2。本次不修改核、原 testbench/golden、数学、布局、ABI、容差或原始 RTL 输出。

## 对应补交清单

| ID | 实际补交 | 限制 |
|---|---|---|
| B06-01 | 实际 XO、candidate.json、kernel.xml、源/头/配置、逐文件 manifest | Git metadata 不替代实际 ZIP |
| B06-02 | 普通五组135个 TV、背压五组135个 TV，共66笔真实 RTL；逐笔独立 expected、可重建回放入口 | 回放消费原始 rtldatafile 的 Y/meta，不重复长仿真，不冒充新 RTL |
| B06-03 | 当前候选收据的精确输入映射、历史 runner、源快照；独立目录新跑冻结基线 full50 Csim 与综合 | 旧初始 tb 原件未恢复，明确保留历史限制；新结果不覆盖旧收据 |
| B06-04 | 从冻结 XO 原样提取完整 csynth/II/接口报告、生成的重叠任务与 AXI RTL；缓存/FIFO适用性说明、32笔背压收据/BFM | HLS slack -0.40 ns 保留，内部 AXI FIFO 占用峰值未测 |
| B06-05 | 342份合成输入/expected/描述文件，40份真实权重回放文件；两份权重及来源/许可；逐文件 SHA和重建检查 | 真实权重激活为固定合成数据，不等于整模型/问诊质量通过 |

## 新目录复测

仅需 Python 3.9+、GCC-compatible C++17 编译器、小端主机，无需 Vitis 许可证、FPGA、原机器 build 目录或预编译 exe。脚本只设置当前进程的编译器搜索路径。

将包解压后，在包根运行。完整检查也可直接针对收到的 ZIP，目标目录必须尚不存在：

```powershell
python tools/check_prefill_supplement.py "收到的B03_A06_补交包.zip" "新的验收目录" --cxx "实际g++.exe路径" --receipt "本次验收.json"
```

该入口核对 CRC/全部载荷 SHA/唯一 XO，在新目录编译回放器，回放66笔 RTL；重新编译候选跑 full50 和真实权重4例；重建全部342+40份固定文件，要求每份 SHA 与已接收文件相同。

只回放已解压的原始 RTL：

```powershell
python tools/replay_prefill_delivery.py --cxx "实际g++.exe路径" --work work/a_rtl_replay --receipt work/a_rtl_replay.json --expected-dir evidence/b03/supplement/rtl_expected --check-expected
```

Linux 可写 `--cxx g++`。最小普通覆盖可加 `--groups smoke gate_t1 gate_t8 down_t1`；包仍保留全部66笔。

回放按原 manifest 验 SHA，解析 HLS TV 的物理总线字节序及记录中的指针偏移，独立展开 B0 行主序矩阵并用 dense INT64/FP32 golden核对，不链接 HLS 核。合法事务检查 Y、padding/输出外窗口和meta；错误事务检查冻结状态优先级、Y不变、计数不递增。临时副本 Y 和 job_id 被故意改错时必须失败，原交付文件保持 SHA 不变。

## 文件位置

- evidence/b03/batches/double/{smoke,gate_t1,gate_t8,down_t1,down_t8}/tv/：两形状T1/T8及30笔边界/错误/重复/尾块原始输入、C输出和实际RTL Y/meta。
- evidence/b03/batches/double/stall_*/tv/：32笔随机背压原始输入/实际输出。
- evidence/b03/supplement/rtl_expected/：从实际输入独立 dense golden 或冻结错误约定生成的逐笔 expected_y/meta/partials。partials只是参考值，未直接探测RTL内部部分和。
- vectors/b03_double/、vectors/b03_double_real/：分别342和40个固定文件。
- vectors/model_source/：两份FP32权重、固定revision、来源/许可。
- evidence/b03/supplement/synthesis/：从冻结XO原样提取的完整报告和生成RTL；成员路径/SHA见 supplement_buffers.json。
- reports/b03/supplement_provenance.json：收据→精确输入映射。
- evidence/b03/supplement/source_snapshots/：关键源/头/tb/cfg/runner原字节快照；initial_runner/及sw32_nominal_runner/保留历史runner。
- evidence/b03/supplement/baseline_refresh/：本次独立构建Csim/综合日志和收据，失败启动记录也保留。

## 缓冲与FIFO适用性

两个权重槽各2048字节、scale槽各128字节；输入缓存38912、token scale 32、累计值1024字节。这是源码容量，不等于实现后BRAM用量。

prefill_overlap的load只写next槽，compute只读current槽；二者完成返回后才交换，最后group禁止预取。任务间没有用户hls::stream队列。原重叠函数综合报告FIFO资源行是“-”，因此用户stream FIFO占用/水位不适用于此结构；数组满/空由槽所有权和完成边界表达。**这不表示AXI master内部FIFO不存在。** 生成AXI RTL已提供，内部FIFO实测峰值保留null。

32笔有限随机背压RTL正常完成提供本配置下动态证据，不能证明所有等待模式的死锁自由。如A另要求AXI内部FIFO峰值，需另约定信号和采样方式；本包不伪造水位。实现、BOARD、整机时延及问诊质量仍未测试。

## 历史追溯

旧baseline synth收据中的root src头是辅助指纹；cfg的实际design source是baseline/b02/src/w4a8_linear_v1.cpp，同目录头原件一直保留。当前double的核、头、tb、golden、cfg输入精确匹配选定收据；普通流程95c40d…稳定runner、背压流程0ec030…runner均随包提供。

旧初始tb SHA f51a3a0d2c62b96239ad82e3a9f3492b94b9dcfdd7eb86ff26c0e0da890dfd00未在本机源码、Git历史/不可达对象或原紧凑包中找到。没有用重建文件冒充原件。为给A可复现的当前基线，本次用冻结baseline源/头和当前tb 699523…在独立目录重跑full50 Csim及综合，两项退出0，命令/脚本/哈希/日志随包提供；新结果不倒签旧证据。

A的static-audit.json未随用户清单提供，本包不代A完成其未提供的全部逐文件差异审计。A可优先复测唯一候选，再独立裁决历史限制。

新基线第一次Csim因本机clang/系统探测程序启动失败，原退出1及日志保留；为当前进程提供既有clang配套DLL后，新独立尝试Csim/综合通过。补交回放工具的TV头解析和Windows中文路径失败尝试另记，不计PASS，原始RTL不变。

包SHA及最终清洁解压收据与ZIP一并提供。六函数库、XRT BO/sync/meta生命周期和平台链接按A07/B04分工另行处理，不扩充本次补交范围。
