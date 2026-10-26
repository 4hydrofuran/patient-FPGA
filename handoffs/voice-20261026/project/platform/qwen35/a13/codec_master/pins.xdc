# 六根信号线保持原针号；两个音频时钟现在仅作输入。
set_property PACKAGE_PIN H12 [get_ports wm8960_bclk]
set_property IOSTANDARD LVCMOS33 [get_ports wm8960_bclk]
set_property PACKAGE_PIN E10 [get_ports wm8960_lrclk]
set_property IOSTANDARD LVCMOS33 [get_ports wm8960_lrclk]
set_property PACKAGE_PIN C11 [get_ports wm8960_adcdat]
set_property IOSTANDARD LVCMOS33 [get_ports wm8960_adcdat]
set_property PACKAGE_PIN D10 [get_ports wm8960_dacdat]
set_property IOSTANDARD LVCMOS33 [get_ports wm8960_dacdat]
set_property SLEW SLOW [get_ports wm8960_dacdat]
set_property DRIVE 4 [get_ports wm8960_dacdat]
set_property PACKAGE_PIN B10 [get_ports wm8960_iic_sda_io]
set_property IOSTANDARD LVCMOS33 [get_ports wm8960_iic_sda_io]
set_property SLEW SLOW [get_ports wm8960_iic_sda_io]
set_property DRIVE 4 [get_ports wm8960_iic_sda_io]
set_property PACKAGE_PIN E12 [get_ports wm8960_iic_scl_io]
set_property IOSTANDARD LVCMOS33 [get_ports wm8960_iic_scl_io]
set_property SLEW SLOW [get_ports wm8960_iic_scl_io]
set_property DRIVE 4 [get_ports wm8960_iic_scl_io]

# 虚拟codec域仅为工具标记外部异步来源；不驱动PL时钟网络。
# 零外部延迟只为CDC分类；异步采样没有相位保证，不能作为电气签核。
create_clock -name codec_virtual -period 651.041667
set_input_delay -clock codec_virtual -max 0.000 [get_ports {wm8960_bclk wm8960_lrclk wm8960_adcdat}]
set_input_delay -clock codec_virtual -min 0.000 [get_ports {wm8960_bclk wm8960_lrclk wm8960_adcdat}]
# 只对三个输入到其第一级D脚约束异步入口；同步后路径必须完整STA。
# XDC只含支持的约束命令；集合唯一性在build.tcl的设计上下文中断言。
set_max_delay -datapath_only 10.000 -from [get_ports wm8960_bclk] -to [get_pins -of_objects [get_cells -hier -regexp {.*sampler/.*reg_bclk_sync_reg\[0\]$}] -filter {REF_PIN_NAME == D}]
set_false_path -hold -from [get_ports wm8960_bclk] -to [get_pins -of_objects [get_cells -hier -regexp {.*sampler/.*reg_bclk_sync_reg\[0\]$}] -filter {REF_PIN_NAME == D}]
set_max_delay -datapath_only 10.000 -from [get_ports wm8960_lrclk] -to [get_pins -of_objects [get_cells -hier -regexp {.*sampler/.*reg_lrclk_sync_reg\[0\]$}] -filter {REF_PIN_NAME == D}]
set_false_path -hold -from [get_ports wm8960_lrclk] -to [get_pins -of_objects [get_cells -hier -regexp {.*sampler/.*reg_lrclk_sync_reg\[0\]$}] -filter {REF_PIN_NAME == D}]
set_max_delay -datapath_only 10.000 -from [get_ports wm8960_adcdat] -to [get_pins -of_objects [get_cells -hier -regexp {.*sampler/.*reg_adc_sync_reg\[0\]$}] -filter {REF_PIN_NAME == D}]
set_false_path -hold -from [get_ports wm8960_adcdat] -to [get_pins -of_objects [get_cells -hier -regexp {.*sampler/.*reg_adc_sync_reg\[0\]$}] -filter {REF_PIN_NAME == D}]
# DAC只约束片内寄存器到pad的路由预算。板外建立/保持及走线必须另测。
set_max_delay -datapath_only 20.000 -from [get_cells -hier -regexp {.*serial/.*dacdat_o_reg$}] -to [get_ports wm8960_dacdat]
