# 新codec-master硬件的独立离线诊断。静态交付门禁未通过时不允许部署。
set_param general.maxThreads 2
if {[version -short] ne "2026.1"} {error "2026.1 required"}
if {[llength [get_parts -quiet xck26-sfvc784-2LV-c]] != 1} {error "Exact K26 part missing"}
set src [file dirname [file normalize [info script]]]
proc assert_audio_constraints {stage} {
    set receipt [open "./${stage}_CONSTRAINT_ASSERTIONS.txt" w]
    foreach {port stem} {wm8960_bclk bclk wm8960_lrclk lrclk wm8960_adcdat adc} {
        set expression [format {.*sampler/.*reg_%s_sync_reg\[0\]$} $stem]
        set first [get_cells -hier -regexp $expression]
        if {[llength $first] != 1} {error "Expected one first-stage register for $port: $first"}
        set destination [get_pins -of_objects $first -filter {REF_PIN_NAME == D}]
        if {[llength $destination] != 1} {error "Missing unique D pin: $first"}
        set endpoints [all_fanout -flat -endpoints_only -from [get_ports $port]]
        if {[llength $endpoints] != 1 || [get_property NAME $endpoints] ne [get_property NAME $destination]} {error "Raw asynchronous fanout escaped first stage: $port $endpoints"}
        set path [get_timing_paths -delay_type max -from [get_ports $port] -to $destination -max_paths 1]
        if {[llength $path] != 1 || abs([get_property REQUIREMENT $path] - 10.0) > 0.001} {error "10ns input datapath constraint missing for $port"}
        puts $receipt "$port first=$first requirement_ns=[get_property REQUIREMENT $path] slack_ns=[get_property SLACK $path]"
        foreach bit {0 1 2} {
            set synchronizer [get_cells -hier -regexp [format {.*sampler/.*reg_%s_sync_reg\[%d\]$} $stem $bit]]
            if {[llength $synchronizer] != 1 || ![get_property ASYNC_REG $synchronizer]} {error "Missing ASYNC_REG: $stem $bit"}
            puts $receipt "ASYNC_REG $synchronizer"
        }
    }
    set transmitter [get_cells -hier -regexp {.*serial/.*dacdat_o_reg$}]
    if {[llength $transmitter] != 1} {error "Missing unique DAC register: $transmitter"}
    set path [get_timing_paths -delay_type max -from $transmitter -to [get_ports wm8960_dacdat] -max_paths 1]
    if {[llength $path] != 1 || abs([get_property REQUIREMENT $path] - 20.0) > 0.001} {error "20ns DAC datapath constraint missing"}
    puts $receipt "wm8960_dacdat driver=$transmitter requirement_ns=[get_property REQUIREMENT $path] slack_ns=[get_property SLACK $path]"
    close $receipt
    write_xdc -force "./${stage}_EFFECTIVE.xdc"
}
create_project codec_master ./project -part xck26-sfvc784-2LV-c
set_property target_language Verilog [current_project]
add_files -norecurse [glob $src/rtl/*.v]
set editdir ./e/my_project.srcs/sources_1/bd/MPSoC_ext_platform
file mkdir $editdir
file copy ./official/MPSoC_ext_platform.bd $editdir/MPSoC_ext_platform.bd
set editbd [file normalize $editdir/MPSoC_ext_platform.bd]
puts [exec D:/Python/Python314/python.exe -B $src/guard_paths.py $editbd]
add_files -norecurse $editbd
open_bd_design [get_files MPSoC_ext_platform.bd]
foreach cell [get_bd_cells] {if {[file tail $cell] ne "ps_e"} {delete_bd_objs $cell}}
foreach obj [get_bd_nets -quiet] {delete_bd_objs $obj}
foreach obj [get_bd_intf_nets -quiet] {delete_bd_objs $obj}
foreach obj [get_bd_ports -quiet] {delete_bd_objs $obj}
foreach obj [get_bd_intf_ports -quiet] {delete_bd_objs $obj}
set_property -dict [list CONFIG.PSU__USE__M_AXI_GP2 0 CONFIG.PSU__USE__S_AXI_GP6 0 CONFIG.PSU__USE__IRQ0 0 CONFIG.PSU__USE__IRQ1 1] [get_bd_cells ps_e]
foreach key {PFM.AXI_PORT PFM.IRQ} {
    if {[lsearch -exact [list_property [get_bd_cells ps_e]] $key] >= 0} {set_property $key {} [get_bd_cells ps_e]}
}
if {[lsearch -exact [list_property [current_bd_design]] PFM_NAME] >= 0} {set_property PFM_NAME {} [current_bd_design]}
proc ip {v n props} {
    create_bd_cell -type ip -vlnv $v $n
    if {[llength $props]} {set_property -dict $props [get_bd_cells $n]}
}
proc net {args} {
    set pins {}
    foreach name $args {
        set obj [get_bd_pins -quiet $name]
        if {[llength $obj] != 1} {error "Missing/ambiguous pin $name"}
        lappend pins $obj
    }
    connect_bd_net {*}$pins
}
proc axi {from to} {connect_bd_intf_net [get_bd_intf_pins $from] [get_bd_intf_pins $to]}
ip xilinx.com:ip:smartconnect:1.0 ctrl [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 3]
ip xilinx.com:ip:smartconnect:1.0 mem [list CONFIG.NUM_SI 3 CONFIG.NUM_MI 1]
ip xilinx.com:ip:proc_sys_reset:5.0 rst_axi [list]
ip xilinx.com:ip:xlconstant:1.1 locked [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 1]
ip xilinx.com:ip:xlconstant:1.1 keep [list CONFIG.CONST_WIDTH 4 CONFIG.CONST_VAL 15]
ip xilinx.com:ip:axi_gpio:2.0 csr [list CONFIG.C_GPIO_WIDTH 32 CONFIG.C_ALL_OUTPUTS 1 CONFIG.C_IS_DUAL 1 CONFIG.C_GPIO2_WIDTH 32 CONFIG.C_ALL_INPUTS_2 1]
ip xilinx.com:ip:axi_dma:7.1 dma [list CONFIG.c_include_sg 1 CONFIG.c_include_mm2s 1 CONFIG.c_include_s2mm 1 CONFIG.c_addr_width 32 CONFIG.c_m_axis_mm2s_tdata_width 32 CONFIG.c_s_axis_s2mm_tdata_width 32 CONFIG.c_m_axi_mm2s_data_width 64 CONFIG.c_m_axi_s2mm_data_width 64 CONFIG.c_sg_length_width 23 CONFIG.c_include_mm2s_dre 0 CONFIG.c_include_s2mm_dre 0 CONFIG.c_sg_include_stscntrl_strm 0]
ip xilinx.com:ip:axi_iic:2.1 iic [list CONFIG.IIC_FREQ_KHZ 100]
ip xilinx.com:ip:xlconcat:2.1 irq [list CONFIG.NUM_PORTS 5 CONFIG.IN4_WIDTH 4]
ip xilinx.com:ip:xlconstant:1.1 zero [list CONFIG.CONST_WIDTH 4 CONFIG.CONST_VAL 0]
create_bd_cell -type module -reference audio_input_sampler sampler
create_bd_cell -type module -reference audio_serial_slave serial
axi ps_e/M_AXI_HPM0_FPD ctrl/S00_AXI
axi ctrl/M00_AXI csr/S_AXI
axi ctrl/M01_AXI dma/S_AXI_LITE
axi ctrl/M02_AXI iic/S_AXI
axi dma/M_AXI_MM2S mem/S00_AXI
axi dma/M_AXI_S2MM mem/S01_AXI
axi dma/M_AXI_SG mem/S02_AXI
axi mem/M00_AXI ps_e/S_AXI_HP3_FPD
net ps_e/pl_clk0 ps_e/maxihpm0_fpd_aclk ps_e/saxihp3_fpd_aclk ctrl/aclk mem/aclk rst_axi/slowest_sync_clk csr/s_axi_aclk dma/s_axi_lite_aclk dma/m_axi_mm2s_aclk dma/m_axi_s2mm_aclk dma/m_axi_sg_aclk iic/s_axi_aclk sampler/i_clk serial/i_clk
net ps_e/pl_resetn0 rst_axi/ext_reset_in
net locked/dout rst_axi/dcm_locked
net rst_axi/peripheral_aresetn ctrl/aresetn mem/aresetn csr/s_axi_aresetn dma/axi_resetn iic/s_axi_aresetn sampler/i_rstn serial/i_rstn
net csr/gpio_io_o serial/i_control
net serial/o_status csr/gpio2_io_i
net sampler/o_rise serial/i_rise
net sampler/o_fall serial/i_fall
net sampler/o_channel serial/i_channel
net sampler/o_sample serial/i_sample
axi dma/M_AXIS_MM2S serial/S_AXIS
axi serial/M_AXIS dma/S_AXIS_S2MM
net keep/dout dma/s_axis_s2mm_tkeep
foreach {port pin direction} {wm8960_bclk sampler/i_bclk I wm8960_lrclk sampler/i_lrclk I wm8960_adcdat sampler/i_adcdat I wm8960_dacdat serial/o_dacdat O} {
    create_bd_port -dir $direction $port
    connect_bd_net [get_bd_pins $pin] [get_bd_ports $port]
}
make_bd_intf_pins_external [get_bd_intf_pins iic/IIC]
set_property name wm8960_iic [get_bd_intf_ports IIC_0]
net dma/mm2s_introut irq/In0
net dma/s2mm_introut irq/In1
net iic/iic2intc_irpt irq/In2
net serial/o_irq irq/In3
net zero/dout irq/In4
net irq/dout ps_e/pl_ps_irq1
assign_bd_address
foreach {cell address} {csr 0xA1000000 dma 0xA1020000 iic 0xA1030000} {
    set segment [get_bd_addr_segs -of_objects [get_bd_addr_spaces ps_e/Data] -filter "NAME =~ *SEG_${cell}_*"]
    if {[llength $segment] != 1} {error "Ambiguous control address: $cell $segment"}
    set_property offset $address $segment
    set_property range 64K $segment
}
validate_bd_design
if {[get_property CONFIG.C_EXT_RESET_HIGH [get_bd_cells rst_axi]] != 0} {error "Reset polarity changed"}
save_bd_design
puts [exec D:/Python/Python314/python.exe -B $src/guard_paths.py $editbd]
write_bd_tcl ./codec-master-bd.tcl
report_ip_status -file ./IP_STATUS.txt
generate_target all [get_files MPSoC_ext_platform.bd]
set wrapper [make_wrapper -files [get_files MPSoC_ext_platform.bd] -top]
add_files -norecurse $wrapper
set_property top MPSoC_ext_platform_wrapper [current_fileset]
add_files -fileset constrs_1 -norecurse $src/pins.xdc
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
open_run synth_1
assert_audio_constraints SYNTH
set io [open ./SYNTH_IO_ASSERTIONS.txt w]
foreach {port pin direction} {wm8960_bclk H12 IN wm8960_lrclk E10 IN wm8960_adcdat C11 IN wm8960_dacdat D10 OUT wm8960_iic_sda_io B10 INOUT wm8960_iic_scl_io E12 INOUT} {
    set obj [get_ports -quiet $port]
    if {[llength $obj] != 1 || [get_property PACKAGE_PIN $obj] ne $pin || [get_property DIRECTION $obj] ne $direction || [get_property IOSTANDARD $obj] ne "LVCMOS33"} {error "IO mismatch: $port"}
    puts $io "$port $pin $direction LVCMOS33"
}
close $io
report_cdc -details -file ./SYNTH_CDC.rpt
close_design
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed"}
open_run impl_1
assert_audio_constraints ROUTED
file mkdir reports
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file reports/timing.rpt
report_cdc -details -file reports/cdc.rpt
report_cdc -summary -file reports/cdc_summary.rpt
report_drc -file reports/drc.rpt
report_route_status -file reports/route.rpt
report_utilization -file reports/utilization.rpt
report_clock_interaction -file reports/clock_interaction.rpt
report_clocks -file reports/clocks.rpt
report_io -file reports/io.rpt
report_methodology -file reports/methodology.rpt
report_exceptions -coverage -file reports/exceptions.rpt
set review [open reports/control_paths.txt w]
foreach target {s_axis_tready_o m_axis_tdata_o m_axis_tlast_o reg_tx_command reg_rx_command reg_rx_channel reg_tx_frame flag_tx_pending reg_tx_shift cnt_tx_period reg_rx_right cnt_watchdog reg_fault} {
    set cells [get_cells -hier -regexp [format {.*serial/.*%s_reg(\[[0-9]+\])?$} $target]]
    if {[llength $cells] == 0} {error "Exception-review target not found: $target"}
    set paths [get_timing_paths -delay_type max -to [get_pins -of_objects $cells -filter {REF_PIN_NAME == D}] -max_paths 1]
    if {[llength $paths] != 1} {error "Exception-review path not timed: $target"}
    puts $review "$target registers=[llength $cells] slack_ns=[get_property SLACK $paths] requirement_ns=[get_property REQUIREMENT $paths]"
    report_timing -delay_type min_max -to [get_pins -of_objects $cells -filter {REF_PIN_NAME == D}] -max_paths 3 -file "reports/path_${target}.rpt"
}
close $review
write_checkpoint ./codec_master_routed.dcp
write_hw_platform -fixed -include_bit ./codec_master.xsa
puts "A13_IMPLEMENTATION_FINISHED_SEPARATE_CDC_TOPOLOGY_REVIEW_REQUIRED"
