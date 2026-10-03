# A07/B04 对齐与部分交付 — 2026-10-03

结论：**PARTIAL；A07尚未通过，B04联合G1～G6未签核，BOARD NOT_TESTED。**

读取远端 `b/qwen35-compute@9a75600e0df8816f4b9134b5c39d67965310dcd3` 的A07/B04分工、A_DELIVERY、KERNEL_ADAPTER及实际profile/meta。接受A维护共享运行时/平台、B维护核/组装候选的边界；不代B签核、不合并B整仓。保留所有旧工程/模型/证据。

## 实际变更

- `modules/linear_A/xrt/host_contract.cpp`：错误meta也核对done/count/算法字节，uint64计数按冻结核模2^64语义回绕。
- `backend.cpp`：修正selected_build_id字段；配置路径相对配置文件；注册表共享所有权保护close/API并发的对象寿命；新非法调用不暴露上次可消费输出；报告读取核私有回显，不把主机常量当实测。
- `host.cpp`：独立六函数消费者，手算输入/输出、显式不可用模式，POISONED不自动退出释放未知DMA资源；本次只交叉构建，未执行ARM程序。
- `platform/qwen35/a07/b04/`：精确Git对象接收、XO参数核查、B原始meta回放、可搬移构建、链接门禁、平台候选、部分交付打包。
- `release/a07_b04_v1/`：实际源码快照、JSON依赖头/许可、B接口资料与66笔二进制meta、A53库/host、实际日志、逐文件SHA。未含模型/SDK/许可证/系统镜像。

## 命令与结果

完整argv/cwd/exit/stdout/stderr见同目录命令JSON，真实编译见包内reports/stdout.txt、stderr.txt。

| 入口 | 退出码 | 结论 |
|---|---:|---|
| intake.py，固定Git commit只取接口材料 | 0 | 字节保存并SHA；未合并B |
| check_contracts.py / qwen35_config.py（前/后） | 0 | 公共/历史契约未改变 |
| 首次build_queue run-next | 1 | 另一个A06任务占锁；没有并发构建 |
| 精确失败队列归档尝试 | 1 | 对方已清理active；本任务未移动或删除队列文件 |
| 再次run-next→run_local.sh→build_portable.sh | 0 | 独立inputs工作目录，正常+sanitizer，真实A53编译 |
| audit_interface.py | 0 | 实际XO/XML/profile及A的17个set_arg映射一致 |
| collect.py | 0 | 253个清单成员、9个SDK动态依赖，ELF AArch64/六导出 |
| link_offline.py前置门禁 | 3 | A06未冻结；v++未执行，非链接失败/通过 |
| B原始b04_a_preflight.py | 1 | 缺xclbin明确拒绝；与PARTIAL状态一致 |

## 分域与联合门

- PC：970项生产共用主机规则通过；同套ASan/UBSan通过。
- PC归档回放：B66笔实际RTL meta、396个篡改拒绝、4个build_id非法值通过；同套sanitizer通过。不是新Cosim，未执行假核。
- ARM64交叉构建：新共享库和独立host通过，Cortex-A53，strict FP，无native；9个依赖在已安装匹配SDK内找到并记录SHA，XRT废弃API告警保留。
- 新共享库SHA256：`4421ca81f1ffc8f4e1e722712af59765383aed91dc0f79ca71007833c7e1ae00`。
- 新host SHA256：`57d4ee54e96d2d191de8fbe6cc8e09caaec668c49d0448303c06a8ce8248a4c0`。
- Csim/Cosim/综合：本轮未执行；A06已有证据独立保留。新版本本地Csim许可证问题仍归A，不归B核缺陷。
- 实现、ARM执行、BOARD：NOT_TESTED；BO预算/地址、板端误差/时延/功耗均null。
- G1：A侧静态ABI/XO和meta回放通过，待B联合确认。
- G2/G3：主机规则通过，但完整实际XRT/故障注入/并发执行未验收；新增close保护只完成源码审阅与交叉编译，不扩大测试结论。
- G4：BLOCKED_A06_LICENSE；无目标xclbin、WNS/DRC/CDC，不拿vadd替代。B HLS slack −0.40ns保留风险。
- G5：库/独立host交叉构建通过；完整S1使用既有A07证据，不重复编译，未声明模型消费PL。
- G6：本机独立快照构建通过，提供可访问包；B侧独立重建/完整候选仍待，不代签。

## 下一步与责任

1. A/用户解决稳定官方许可证绑定；不要反复重启WSL。当前MAC `00155dbc207a`，曾绑定`00155dbc2453`，并未修改MAC/许可证。
2. A06同版本本地Csim通过并正式冻结后，A在唯一队列执行真实v++链接/实现及报告审查；不擅自开启门禁。
3. A补完整调用层故障路径测试，B使用本包构建/适配；完整xclbin清单补齐后再跑B preflight和联合评审。
4. 到板启动/内存/XRT/恢复与A12结果消费另验收。

本次不把200轮/模型量化重跑，不改B核、不动SD/QSPI。上传范围为本A07候选和证据，不含当前脏树其他未提交工作。Git上传回执另存publish.json，不能在推送前宣称已上传。
