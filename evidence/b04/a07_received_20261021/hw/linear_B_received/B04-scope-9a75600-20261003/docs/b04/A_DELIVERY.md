# A07 接入 B04：交付及复核入口

用户已决定先完成 B 侧工作。A 尚未交付；本轮记录的是实际依赖缺失，不是 A 已失败或 A 已通过。完整 B04 需要 A 的共享成果和 A/B 联合验收。

## A 提供的内容

- 公共调用层全部源码、冻结公共头、构建入口和可分发依赖说明；源码提交或其他可核实版本。
- double 核适配的 BO/group_id/sync 和 meta 实现，生命周期及权重驻留实现。
- 正常调用及非法参数、短缓冲、无效句柄、并发、异常、超时/poisoned、安全关闭、stale meta 的实际控制测试与原日志。mock 明确标记，不能记为 FPGA_REAL。
- 匹配 double XO 的实际 xclbin、链接配置、工具/平台记录、真实时序和资源报告、链接日志及退出状态。
- 匹配目标 sysroot/XRT 的 ARM64 `.so` 和独立 host，构建日志、ABI/依赖检查及退出状态。

## 预检查描述文件

在 A 交付根目录保存 `a_delivery.json`。以下是格式示意，尖括号内容需替换为真实记录；此示意不算产物或验收证据。

```json
{
  "source_revision": "<真实A源码版本>",
  "public_contract_sha256": "83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6",
  "kernel_build_id": "0xB3030002",
  "xo_sha256": "96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23",
  "artifacts": {
    "public_header": {"path": "contracts/sp_linear_v1.h", "sha256": "<实际文件摘要>"},
    "runtime_source": {"path": "runtime/<主入口源码>", "sha256": "<实际文件摘要>"},
    "build_entry": {"path": "runtime/<构建入口>", "sha256": "<实际文件摘要>"},
    "dependency_notes": {"path": "runtime/<完整源码清单和依赖说明>", "sha256": "<实际文件摘要>"},
    "xclbin": {"path": "artifacts/<实际xclbin>", "sha256": "<实际文件摘要>"},
    "arm64_library": {"path": "artifacts/<实际.so>", "sha256": "<实际文件摘要>"},
    "arm64_host": {"path": "artifacts/<实际host>", "sha256": "<实际文件摘要>"},
    "link_config": {"path": "config/<链接配置>", "sha256": "<实际文件摘要>"},
    "platform_profile": {"path": "config/<真实平台和工具记录>", "sha256": "<实际文件摘要>"},
    "implementation_report": {"path": "reports/<实现报告>", "sha256": "<实际文件摘要>"},
    "link_log": {"path": "reports/<链接日志>", "sha256": "<实际文件摘要>"},
    "arm_build_log": {"path": "reports/<ARM构建日志>", "sha256": "<实际文件摘要>"},
    "control_test_receipt": {"path": "reports/<控制测试收据>", "sha256": "<实际文件摘要>"}
  }
}
```

所有路径位于交付目录中；不能引用未移交的本地 build 文件。`runtime_source` 是主入口，不是允许只交一个源文件；其余源码、包含文件、入口及依赖必须按完整清单实际移交。日志须包含执行命令和退出状态，保留失败尝试。

```text
python tools/b04_a_preflight.py <A交付目录> --readelf <已有aarch64-linux-gnu-readelf路径> --receipt reports/b04/a_preflight.json
```

工具拒绝缺文件、摘要/契约/核身份不一致、非 ARM64 ELF、缺失或未定义公共导出。它对实际二进制运行 readelf。**预检查不验证 xclbin 内核身份、实现时序、XRT 实际行为，也不自动相信日志中的 PASS 字样。**这些内容需要下一阶段在实际 A 源码、元数据和原日志上复核。

## B 接收后按顺序完成

1. 保存原 A 交付，不覆盖失败记录。核对完整源码、依赖和文件摘要，再运行预检查。
2. 复核公共函数实现及 B 核参数/BO group；对实际 xclbin 读取内核与连接元数据，不把参数索引当作内存组。
3. 以固定独立向量运行正常、重复、错误及异常路径；核对 meta、报告 execution_kind 和未测 null。
   `vectors/b04_meta/manifest.json` 提供66笔原始完成样例和独立 expected，可用于 A 的解析器测试；不能用这些归档记录替代实际 XRT 生命周期测试。
4. 核对真实实现时序/资源、平台与时钟，以及 ARM64 库和 host 的 sysroot/XRT 配套。
5. A/B 逐项复核 G1～G6，记录产出方、版本、摘要、执行类型和证据；缺项保持待完成。
6. 满足上述条件后再组装完整 `B_pc_candidate_v1.zip`，在独立目录完整复测。BOARD 仍保持 NOT_TESTED，进入 B05 需另具备实板条件。

本轮 B 阶段工具只组装部分交付，未实现或代签 A 的运行时。完整候选组装中的 A 产物合并与 G1～G6 测试入口将在收到真实交付后完成，避免凭不存在的接口假设编写适配。
