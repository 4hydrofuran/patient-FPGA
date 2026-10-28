# A07 / B04 接续差距（2026-10-03）

依据远端 `9a75600e0df8816f4b9134b5c39d67965310dcd3` 分工文件；采用 A 公共运行时/平台、B 计算核/候选组装的边界，不代签 B。

| 项目 | 处置与证据范围 |
|---|---|
| 六函数、BO所有权、权重常驻、group_id、同步、POISONED | 已有实现；旧969项PC主机逻辑与ARM构建有效。本次补元数据及生命周期缺陷，须新构建 |
| 错误meta的done/count/字节检查，uint64回绕 | 必须补实现与B实际归档复测；不得因status非零提前跳过校验 |
| selected_build_id与配置相对路径 | 必须修复；公共C ABI不变 |
| close与并发API的对象寿命 | 必须修复注册表共享所有权；完整实际XRT并发/驱动异常仍待测试 |
| B独立目录可取得源码和依赖 | 必须补可搬移构建入口、冻结B资料和hash、JSON头许可、独立ARM host |
| 目标xclbin、WNS/DRC/CDC | 必须完成，受A06未冻结阻断；不能拿旧vadd xclbin代替。新link入口拒绝绕过门禁 |
| 模型ARM64 | 已有完整S1 A53构建；本次不修改/重复编译模型，不宣称消费PL结果 |
| 实际BO、timeout/DMA、恢复/BOARD | NOT_TESTED，预算null，不在本阶段伪造 |
| 双缓冲/融合、自动unpoison、更快复用 | P2 NOT_IMPLEMENTED；不冒充本次实现 |

完整A07仍需实际链接/实现报告、完整控制层集成负路径闭环；本次上传若缺这些，必须命名PARTIAL，不向B的完整a_delivery清单塞占位xclbin。
