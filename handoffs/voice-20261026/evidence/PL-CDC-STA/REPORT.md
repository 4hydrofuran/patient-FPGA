# WM8960 codec-master：无板核验报告

结论：无板功能与物理实现核验已完成，含用户授权的13条操作数逐项例外；严格自动风格门禁仍未整体通过。
不是上板放行：BOARD=NOT_TESTED，未连接板卡、加载位流、安装模块、录音或试音，电流仍null。

## 实际完成的层级

| 层级 | 结果与范围 |
| --- | --- |
| Python语义模型 | 5项原有测试；1024帧独立向量；源码连续性以每次INPUTS.json核对 |
| 新时钟离散模型 | 4项：四拍等待扫查、两拍负例、正窗口与慢系统时钟拒绝；MTBF未测 |
| 真实RTL仿真 | xsim2026.1 s05；520帧双向逐位比较、2周期TLAST、5类故障；额外偏斜/回压/清错/重同步/复位检查 |
| 综合／布局布线 | Vivado2026.1 b05，xck26-sfvc784-2LV-c；实际bit/XSA/routed DCP，BD关键警告0，布线错误0；外层后处理exit1保留，p04同一DCP补验exit0 |
| 时序 | WNS=5.629ns，TNS=0.000ns；WHS=0.010ns，THS=0.000ns；WPWS=3.500ns |
| CDC | 原始约束报告及clock interaction保留；9个音频ASYNC_REG、逐级直连/唯一扇出/同钟证书及6条级间min/max；另有仅分析用的5条Info拓扑视图，未报告Warning/Critical |
| 驱动 | 3个真实AArch64模块、vermagic6.8.12-a10irq2；真实内核格式翻转PC执行7项，DMA地址/周期C拒绝条件执行11项；未probe或装载 |
| 设备树 | 在原irq2备份上真实编译/合并，全部11个新增节点disabled；实际HWH核对地址、IRQ、时钟、完整流接口 |
| 文档工具 | WaveDrom3.6.1实际渲染三个模块规格；技能包隔离短路径本地自检通过，不代表项目RTL风格通过 |
| BOARD／电气／声学 | 全部NOT_TESTED，完整PS/DDR/AXI DMA协同仿真也未运行 |

## 逐项例外与工具局限

见EXCEPTIONS.md及OFFLINE_REVIEW.json。13条VG146原始FAIL不删除，操作预算仍为3；每条都有同源重仿真及真实min/max和CDC证据。
额外VG066导航注释、VG084 concat求宽与10条VG138属性字符串问题保留原判定，补充评审不改写严格门禁。

| 原始公开门禁 | 状态 |
| --- | --- |
| compile | passed |
| ast | passed |
| readability | failed |
| comment | passed |
| naming | passed |
| profile | passed |
| testbench | not_requested |
| toolchain | not_requested |

上表testbench/toolchain的not_requested是静态门禁自身的状态；实际xsim/综合/实现证据单独列在上方，不能互相冒充。

## 保留的失败与修复

- b01：BD实例名config为HDL保留字，未综合；更名csr，旧输入/退出码保留。
- b02：XDC中的foreach/if未被正式接受，三个异步入口产生负余量；位流虽生成仍判失败，不继承其时序。
- b03：两拍等待版得到正STA，但离散相位反例显示跨链等待偏紧；后来四拍版重新仿真、综合实现。
- b03/b04：逐根信号接通而正式AXIS元数据/接口连接不完整，3条BD关键警告保留；最终版完整S_AXIS/M_AXIS消除。
- b04：一个AMD Tcl app-loader子任务在create_project阶段报Could not open C for writing，未进入该模块综合；真实退出后仅归档本任务预约。原因未据此证明，未修改安装环境；最终版使用干净工程默认缓存重建。
- b05：实现及XSA/DCP导出完成后，补充CDC脚本的reset_path命令不受支持，外层exit1原样保留；p01/p02只有IIC报告、音频拓扑未被自动覆盖，复核拒绝；p03实际获得全部5条Info及网表证书，但min_max/max_paths1仅选出保持路径，复核再次拒绝；p04分别报告12条setup/hold路径后通过，未改逻辑或重导出。
- 驱动最初派生导出标记及DAI probe API不匹配、CPU端主从格式未翻转均保留；v4修格式，v5增加32位起始地址与对齐拒绝，避免u64加法回绕绕过检查；旧格式和旧回绕反例被真实C执行复现。
- HWH检查器最初把0x0与0作字符串比较；修成整数比较并检查真实参数名，原失败保留。
- 完整AXIS绑定后，HWH将可选TKEEP省略于DMA的PORTS；从4位常量源的CONNECTIONS核对目标及15数值，并保留生成HDL，先前StopIteration失败保留。
- 文档提取器误认task形参及属性；采用同一formatter AST核对真实设计端口，正式no-source入口渲染已确认合同，不伪造端口。
- 技能包长路径失败及收集器误用stdout.log失败保留；分别在隔离短路径、正确stdout.txt下补验，不改安装技能。

## 仍不放行的项目

保留4条IIC缺外部延迟、3条零分类延迟等methodology提示，以及PS/SmartConnect AWUSER/ARUSER元数据宽度提示和供应商优化告警。
不填虚假IIC电气延迟，不豁免新的板端告警。实际IIC边沿/上拉、电压/电流、24MHz与PLL、BCLK/LR及板外setup/hold、Linux DMA/IRQ和恢复仍需静默实测。
p03的BCLK源自身输入延迟被忽略提示保留；p04仅对LR/ADC设置分类延迟。重读原约束的供应商waiver重复提示保留，拓扑报告使用-no_waiver；分析视图没有被用于STA、实现或导出。
对应原因及安全方法见source-final/MEASUREMENTS.md。当前永久EPERM驱动及disabled设备树不得直接改字段解锁开流。

## 回滚与产物

实际工具快照和每次INPUTS、completion、日志见native-tools；最终产物在native-tools/b05/artifacts，禁止本轮加载。
XSA SHA256：`27412daeb18a8575608832da8b437c2c5202c814690f120eac2ea030eaeedefb`。
routed DCP SHA256：`742aa87ba82654034c96639aa8cc8c32184b704c71ddffa1b5693b02342f9c83`。
旧a06、982项旧封存证据及2266项私有TTS包校验保持不变；不复制或发布权重。共享文档仅新增本轮A13内容，不覆盖TT10。
没有本轮板端变更需要撤销。未来回滚不能盲目加载输出时钟的旧a06，必须先解除与codec master的双驱动风险。
下一步仍等待另一任务独立后检及明确释放，并在新鲜身份、原件备份、唯一租约/双锁和新的调试窗口下推进；本轮不自动进入BOARD。

actual_model_settings=unknown；无协作子代理；DeepSeek只用于固定引脚表文本，不参与架构、RTL、驱动或证据验收。
