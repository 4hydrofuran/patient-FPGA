# 保持六根线和24MHz的时钟／CDC复核

WM8960为BCLK及DACLRC提供者，PL两脚只输入，板上24MHz不拆、MCLK不外接。
ALRCGPIO=1使ADC/DAC共享DACLRC，采样率同源；PS约100MHz只是过采样与传输时钟。
不存在另一个独立48k采样发生器，也未复用不支持slave的旧AMD I2S/Audio Formatter。

## 输入路径与重汇合

三个单bit输入各用三级ASYNC_REG；原始输入只能扇出到自己的首级D脚。BCLK随后
额外等待四拍，再注册边沿事件；LR/ADC从各自隔离链末级再寄存，串行引擎下一拍
译码、再执行。输出DAC位由单个寄存器在检测到低相后更新，I2S边界拍仍输出旧字LSB。

原两拍等待版的失败反例已保留：假设LR传播10ns、片内/板路相对偏斜另10ns，
LR同步比BCLK多一次系统捕获周期，在101MHz及某些相位下，发送译码可能尚读不到
新的LR。clock_budget.py的负例不能被旧520帧固定相位仿真覆盖。四拍版对99–101MHz、
101个相位和三组传播偏斜作离散模型核对，并配合真实xsim相位走查及非零回压复测。
额外一次捕获周期是明确假设，不是声称亚稳态必在一拍消失；MTBF仍null。

闭式边界也单独核对：系统周期T在约9.901..10.101ns，输入相对延迟不超过20ns时，
两路首次捕获拍差最多ceil(20/T)，再加一次额外LR捕获假设，合计最多4拍。
LR对外Q在其首次捕获后3拍稳定，TX译码在BCLK首次捕获后D+4拍读取旧Q；
采用D=4时至少早一个系统周期稳定。此推导对任意采样相位成立，但前提中的板路
延迟与额外捕获上界仍须分别通过物理测量和可靠性评审核实，不能当作硬件事实。

## 有条件的TX窗口

固定16位槽、32BCLK/帧。假设codec频差+500ppm、高低相各至少周期40%，系统最低
99MHz：最短低相约260.287ns。输入首级D预算10ns、包含一次额外捕获假设的流水
11系统拍、DAC寄存器到pad预算20ns、器件setup10ns，剩余线缆/额外抖动预算约
109.175ns。它不是测得的109ns裕量。32位槽不在本候选的固定配置内。

## 约束边界

真实实现仅把三个异步输入至各自首级D限定为max_delay datapath_only 10ns，
不对同步后的逻辑放宽；DAC寄存器至pad限定20ns。虚拟codec时钟与零外部延迟只作
来源分类，不提供相位保证，也不伪造未知走线。所有系统域路径仍按约100MHz核验。
XDC只保留支持的约束命令，集合唯一性、9个ASYNC_REG和输入扇出在Tcl设计上下文断言。

原始report_cdc不列出仍带max-delay的三个音频入口，原始clock-interaction将其
列为Ignored/Max Delay Datapath Only；不能把只看到两条IIC Info误认为已覆盖全部
CDC。另从同一SHA的routed DCP建立纯分析内存视图：先报告原始STA/CDC，再用
reset_timing重读已写出的原约束（精确移除这三个入口max-delay），只对其首级D
改设false-path，并在分析视图标记实际BCLK源管脚时钟、给LR/ADC添加分类延迟，
以展示同步拓扑。另在修改视图前，逐一验证9个同步FF的同钟、属性、唯一扇出和Q-D
直连，分别报告6条级间连接的setup/hold。分析视图报告不能作为时序证据，不能用于实现或重新导出
位流；原始约束、STA、DCP和XSA仍保持不变。

IIC由AMD IP的四级输入同步处理，100kHz、额外惯性延迟0；IIC模拟边沿、上拉及
板外setup/hold必须实测。不向缺少实测的IIC引脚填入虚假外部延迟来消除工具警告。

依据：[WM8960主模式时序，第14页](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/307/WM8960.pdf)、
[AMD CDC报告规则](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Understanding-the-Clock-Domain-Crossings-Report-Rules)。
