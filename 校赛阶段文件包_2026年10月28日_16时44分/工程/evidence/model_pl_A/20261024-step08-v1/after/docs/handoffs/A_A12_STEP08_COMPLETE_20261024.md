2026-10-24 A12第08步完成（有限范围、保留限制）：24层72投影完整诊断，216次真实PL返回Y及消费者核验通过；逐层输入输出、节点、10行logits和混合状态与同板S1逐位一致。冻结开发集17条同板CPU/PL自然生成配对通过，PL实际25776次；7条策略模板单列为PC无模型，原始语言检查{'pass': 17}，医学审核未完成。每窗口72份权重只加载一次、148BO共140591104B复用；两窗口worker/manager正常exit0，默认PL/GDM恢复，独立及延时复核无ZOCL/设备用户/锁/active lease。一次正常重启仅FSBL的失败保留，专项授权冷启动恢复irq2，默认启动文件不变；直连使用未保存NM配置。06旧FAIL保留；正常生成关闭逐调用Y诊断账，216次重诊断证明单列。默认FPGA未启用，物理峰值/硬件全局计数/加速比null；09未启动。报告 `evidence/model_pl_A/20261024-step08-v1/REPORT.md`。下方为历史快照。

# A12 第08步：全模型真实PL消费与自然生成

状态：PASS_A12_STEP08_FULL_MODEL_BOARD_WITH_LIMITATIONS。执行日期（北京时间）：2026-10-24T11:31:43.526528+08:00。

## 实板结果

诊断窗口覆盖24层gate/up/down共72投影，实际216次真实PL调用，job1—216，每投影T8/1/1。逐次ERT=4、build0xB3030002、raw64Bmeta、job回显、原始Y摘要与GLU/残差消费者关联全部通过。不是仅有调用而未消费。原始216份输入/输出、10行全词表logits、诊断节点和20312900B混合状态与同板同一ARM产物S1逐位一致；算子1e-4+1e-5*abs(ref)、整图.002+.0002*abs(ref)门槛未改。PC反事实丢弃Y仍被拒绝。

自然生成使用冻结开发集，17条模型请求，输入PC/ARM分词一致，每条最多24个输出token，final-logits、物理ubatch上限8、R0清空状态；完整17条同板S1/S2的token、文字、EOS、prefill末logits指纹和最终状态指纹一致。实际PL提交25776次，详见GENERATION_AUDIT.json。正常模式关闭逐调用消费者账以避免重诊断二次方拷贝，不能把自然生成每次调用称为已保存Y哈希；重诊断216次消费者证据单独成立。正常final-logits仅请求末位置；当前固定运行时embeddings_nextn_masked未启用，在最后MLP/norm之后选择输出行，MLP仍按全部实际microbatch执行。每条实际完成数与72*(ceil(prompt_tokens/8)+decode_calls)独立核对；不声称省略了最后层MLP。正常生成每层/每调用实际T未逐项留账，不据此宣称09尾块矩阵通过。源码快照见SCHEDULING_SOURCE_qwen35.cpp，调用分账见GENERATION_CALL_ACCOUNTING.json。

7条策略拒绝/澄清模板来源为PC既有策略，不算作BOARD模型生成；模板比例7/24。模型原始有限语法检查：{'pass': 17}，EOS17/17，24token上限但无EOS项：[]。失败或不确定原文及事实、否定、数字核对逐项保存在DEV_QUALITY.json；不替换原文、不以模板或CPU掩盖。有限检查器不是医学审核，医学审核保持PENDING。

## 资源和正常收口

两个独立窗口均实际加载72份权重一次，148显式BO共140591104B；group3、8192字节分配charge、低2GiB、逐BO非重叠、请求前后地址/活权重不变与加载计数稳定通过。稳态不按token重传权重。资源余量与健康采样：

```json
{
  "diagnostic": {
    "manager_exit": 0,
    "worker_exits": [
      0,
      0
    ],
    "normal_restore": true,
    "postchecks": [
      {
        "name": "status_final",
        "kernel_gate": {
          "allowed": true,
          "reason": "NO_NEW_DIAGNOSTIC",
          "previous_sha256": "41a13cd60eb7a1a605ec9c37da7b56379b9752da50136c6963c746b1e9460de3",
          "current_sha256": "41a13cd60eb7a1a605ec9c37da7b56379b9752da50136c6963c746b1e9460de3",
          "new_line_count": 0,
          "new_text": "",
          "diagnostics": []
        },
        "processes_absent": {
          "2738": true,
          "2728": true,
          "2840": true,
          "3067": true
        }
      },
      {
        "name": "delayed_01",
        "kernel_gate": {
          "allowed": true,
          "reason": "NO_NEW_DIAGNOSTIC",
          "previous_sha256": "41a13cd60eb7a1a605ec9c37da7b56379b9752da50136c6963c746b1e9460de3",
          "current_sha256": "41a13cd60eb7a1a605ec9c37da7b56379b9752da50136c6963c746b1e9460de3",
          "new_line_count": 0,
          "new_text": "",
          "diagnostics": []
        },
        "processes_absent": {
          "2738": true,
          "2728": true,
          "2840": true,
          "3067": true
        }
      }
    ],
    "min_MemAvailable_kib": 2931480,
    "min_CmaFree_kib": 644416,
    "max_temperature_mC": 32562,
    "health_samples": 575
  },
  "generation": {
    "manager_exit": 0,
    "worker_exits": [
      0,
      0
    ],
    "normal_restore": true,
    "postchecks": [
      {
        "name": "status_final",
        "kernel_gate": {
          "allowed": true,
          "reason": "NO_NEW_DIAGNOSTIC",
          "previous_sha256": "14b173c7dfc9361f73d23df77cc9b238142bf524508454a0c6f528237f39d8aa",
          "current_sha256": "14b173c7dfc9361f73d23df77cc9b238142bf524508454a0c6f528237f39d8aa",
          "new_line_count": 0,
          "new_text": "",
          "diagnostics": []
        },
        "processes_absent": {
          "5074": true,
          "5067": true,
          "5164": true,
          "10805": true
        }
      },
      {
        "name": "delayed_01",
        "kernel_gate": {
          "allowed": true,
          "reason": "NO_NEW_DIAGNOSTIC",
          "previous_sha256": "14b173c7dfc9361f73d23df77cc9b238142bf524508454a0c6f528237f39d8aa",
          "current_sha256": "14b173c7dfc9361f73d23df77cc9b238142bf524508454a0c6f528237f39d8aa",
          "new_line_count": 0,
          "new_text": "",
          "diagnostics": []
        },
        "processes_absent": {
          "5074": true,
          "5067": true,
          "5164": true,
          "10805": true
        }
      }
    ],
    "min_MemAvailable_kib": 2903888,
    "min_CmaFree_kib": 461368,
    "max_temperature_mC": 34241,
    "health_samples": 38157
  }
}
```

两窗口CPU/PL worker与manager实际exit0；完整FD/VMA/refcount门禁、普通卸载、ZOCL退出、默认PL与GDM恢复、唯一租约归档及双锁释放通过；独立及延时复核均确认无设备用户和已知进程。最终收口扫描尝试次数为{'diagnostic': 2, 'generation': 2}，进程集合/FD表变化导致的不完整读数原样保留，仅后续真正完整的no-users扫描被接受；另用身份、manager start_ticks、期限和预算独立重建租约JSON字节，归档SHA与两次独立后验一致，详见两个LIFECYCLE_SUPPLEMENT。未使用强杀、强卸载、复位或故意DMA故障。主机许可/完成计数不冒充硬件全局计数。

## 恢复与保留失败

起始板卡已回默认1036且无IPv4，未提交模型计算。专项授权的一次正常重启仅观察到FSBL前缀，未进入U-Boot/Linux，失败原文保留、根因未查明。经用户专项授权和实际一次拔电等待5秒再上电，固定COM5捕获启动；RAM加载irq2 FIT及三个组件校验通过后只发送一次临时bootm。未saveenv、未刷写、默认image.fit/boot.scr哈希与前件一致。新boot86e4938b-0f65-4166-9237-c547b67e1451，内核6.8.12-a10irq2。

原始ip addr添加被NetworkManager清除，SSH中途超时保存。改为明确save no/autoconnect no/never-default的临时NM连接，D-Bus Unsaved=b true；没有写永久网络配置。首次空IPv4处理IndexError、脚本参数作用域和排他收据生成失败均保留，见FAILURES.json及network-failed-*。已读回root重启前门禁与唯一systemctl调用收据。

新内核基线已有189行诊断（旧接受快照260行），含既有X.509、pinctrl、TPM等启动限制；比较差异仅X.509告警CPU/寄存器变化，原始日志不删，不称无告警内核。新窗口只接受既有精确动作例外，其余新诊断闭锁。

生成原草稿总1200秒/单次120秒未经执行；短诊断实测PL prefill约32.4秒、decode约26.2秒，表明整套17对正常生成需要更长时间。执行前另存generation-budget-v2.json（总18000秒/接收1200秒），保留原稿，47736总许可/17请求/每条24输出以及所有资源/温度/数值门槛不变。期限到达仍只取消后续交付，不授权kill或释放未知DMA。

## 限制与下一步

06跨ISA整图FAIL、首次容量FAIL与07旧收口FAIL/-9均保留；本轮使用已审阅的同板S1/S2基准。默认计算manifest仍CPU_REFERENCE，未启用默认FPGA；未改公共契约、数学、核、模型或sidecar。物理总峰值、硬件周期/全局计数、功耗、加速比均null。运行耗时含大量诊断/耐久门禁记录，不作为10步公平性能结论。09状态/分块/取消矩阵未执行，10性能和11最终A12收口未完成，医学审核未完成。

全部旧13240文件逐字节保护检查与新封存见HISTORICAL_PRESERVATION.json/SEAL.json。未自动切换模型（实际设置unknown）、未启用子代理、未提交或推送。
