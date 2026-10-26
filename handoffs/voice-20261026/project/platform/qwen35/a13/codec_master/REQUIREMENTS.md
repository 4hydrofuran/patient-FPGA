# A13 新过采样从接口：已确认需求与实现计划

任务类别generate/validate；独立新候选，不修改a06。用户已选WM8960主，保留24MHz
及六信号线。2026.1、xck26-sfvc784-2LV-c、官方kv260_base PS/DDR/MIO配置继承。
初始约束为3.3V总100mA。随后用户确认模块改为外部5V、5VIN跳线、旧J2供电已
断开、共地、信号仍3.3V；实测电流和外部电源容量仍为null。2026-10-25最新
指令限定本轮仅无板核验：不访问板卡、不试音、不录音、不加载或安装，待另一个
任务独立后检和确认释放板卡后另开板端窗口。POWER_STATUS.json保存确认及禁令。

## 需求 → 代码计划 → 规格 → Python语义 → RTL

- 固定48kHz、双声道S16_LE、16bit槽、I2S一位延迟，32BCLK/frame。
- H12/E10只输入；D10输出；C11输入；B10/E12仍IIC，不用作时钟。
- 仅PS约100MHz域；BCLK/LRCLK/ADC各独立同步，延迟后在BCLK高相稳定采样；
  不能把同步后的LRCLK边界当作当前MSB，跨边界LSB属于前一声道。
- AXI DMA scatter-gather、MM2S/S2MM、32bit stream一拍一立体声帧（低16位L）；
  设备帧事件控制消费/生产，没有独立48k计数发生器。
- 环形DMA固定period=256帧/1024B，至少2个period。RX每256帧TLAST；
  TX DMA每period TLAST按256帧检查。不能忽略包长/短包。
- 先采用单帧弹性缓存；在每20.83us期间预取下一帧，ready低时不得覆盖。
  这不是深度FIFO或实时OS保证；饥饿/阻塞必须锁存错误并停止有效音频。
- 检测缺时钟、错误槽宽、TX underrun/RX overrun、错误TLAST；故障必须停止，
  软件STOP后再清除/重新启动。停止清空待发送数据，输出零，不能重放旧帧。
- 寄存器控制与stream同一域；不保留旧formatter多位配置CDC。复位使用专用复位IP。
- 驱动实现DMAengine/ASoC候选，所有对用户可达open/params/trigger永久EPERM，
  无可解锁模块参数；设备树全部disabled。未来放行必须另版源代码和独立验收。

## 深度评审要点

接口：I2S边界与最后一位、AXIS稳定、AXI-Lite独立AW/W握手、32bit内存排列。
复位：先禁流清零，再取消DMA；禁止unknown DMA状态重新开机，当前无板不执行。
时序：100MHz所有寄存器；三输入同步链，不用原始输入驱动逻辑；跨链偏斜以稳定
半周期预算及随机延迟仿真验证，不用全局false-path隐藏同步后逻辑。
宽度：16bit×2=32bit，period8bit计数；固定配置无动态采样率CDC。
覆盖：随机异步相位/占空/同步延迟、LSB跨界、暂停/取消/缺钟、回压/欠载/溢出、
TLAST周期、AXI-Lite通道乱序、复位及重新启动。仿真不是亚稳态MTBF/电气证明。

## 交付矩阵

compile / ast / readability / comment / naming / profile / testbench / toolchain
分别记录；外部xsim、综合、布局布线、CDC/STA与BOARD独立。不因文件存在记PASS。
需要实测：供电总电流/电压、唯一时钟驱动、24MHz/PLL/BCLK/LRCLK、IIC边沿300ns、
串行建立保持、Linux DMA/IRQ/长流/故障恢复。均先NOT_TESTED。
