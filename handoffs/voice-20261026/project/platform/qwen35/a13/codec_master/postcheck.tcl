# 只读打开同一份已实现DCP；只输出报告，不导出或加载修改后的设计。
if {[version -short] ne "2026.1"} {error "2026.1 required"}
set_param general.maxThreads 2
open_checkpoint ./reference/codec_master_routed.dcp
file mkdir reports
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file reports/timing_original.rpt
report_cdc -details -file reports/cdc_original.rpt
report_cdc -summary -file reports/cdc_summary_original.rpt
write_xdc -force reports/ORIGINAL_IMPLEMENTED_CONSTRAINTS.xdc
# 不依赖CDC分类器的真实网表证书：原始管脚仅到第一级D，逐级Q-D直连、同钟、
# ASYNC_REG逐个核对，并保留六条级间min/max报告。此段仍用原始实现约束。
set certificate [open reports/AUDIO_SYNCHRONIZER_NETLIST_CERTIFICATE.txt w]
foreach {port stem} {wm8960_bclk bclk wm8960_lrclk lrclk wm8960_adcdat adc} {
    set previous_q {}
    for {set bit 0} {$bit < 3} {incr bit} {
        set cell [get_cells -hier -regexp [format {.*sampler/.*reg_%s_sync_reg\[%d\]$} $stem $bit]]
        if {[llength $cell] != 1 || ![get_property ASYNC_REG $cell]} {error "Missing unique ASYNC_REG: $stem $bit"}
        set d [get_pins -of_objects $cell -filter {REF_PIN_NAME == D}]
        set q [get_pins -of_objects $cell -filter {REF_PIN_NAME == Q}]
        set c [get_pins -of_objects $cell -filter {REF_PIN_NAME == C}]
        set clocks [get_clocks -of_objects $c]
        if {[llength $clocks] != 1 || [get_property NAME $clocks] ne "clk_pl_0"} {error "Non-system synchronizer clock: $cell $clocks"}
        if {$bit == 0} {
            set endpoints [all_fanout -flat -endpoints_only -from [get_ports $port]]
            if {[llength $endpoints] != 1 || [get_property NAME $endpoints] ne [get_property NAME $d]} {error "Raw input fanout escaped: $port"}
        } else {
            if {[get_nets -of_objects $previous_q] ne [get_nets -of_objects $d]} {error "Combinational logic between sync stages: $cell"}
            set endpoints [all_fanout -flat -endpoints_only -from $previous_q]
            if {[llength $endpoints] != 1 || [get_property NAME $endpoints] ne [get_property NAME $d]} {error "Intermediate synchronizer fanout escaped: $cell"}
            report_timing -delay_type max -from $previous_q -to $d -max_paths 1 -file "reports/sync_${stem}_${bit}_max.rpt"
            report_timing -delay_type min -from $previous_q -to $d -max_paths 1 -file "reports/sync_${stem}_${bit}_min.rpt"
        }
        puts $certificate "$port stage=$bit cell=$cell ASYNC_REG=TRUE clock=clk_pl_0 DIRECT_SINGLE_FANOUT_VERIFIED"
        set previous_q $q
    }
}
close $certificate
# report_cdc不会展开仍带max-delay的端点。重建仅分析用内存视图，精确移除
# 三个音频入口max-delay，其他原约束全部重读；原始STA及DCP绝不改写。
set input [open reports/ORIGINAL_IMPLEMENTED_CONSTRAINTS.xdc r]
set original [read $input]
close $input
set output [open reports/TOPOLOGY_BASE_NOT_FOR_IMPLEMENTATION.xdc w]
set removed 0
foreach line [split $original "\n"] {
    if {[regexp {^set_max_delay .*get_ports wm8960_(bclk|lrclk|adcdat)} $line]} {
        incr removed
    } else {
        puts $output $line
    }
}
close $output
if {$removed != 3} {error "Expected exactly three audio max-delay diagnostic removals: $removed"}
reset_timing
read_xdc reports/TOPOLOGY_BASE_NOT_FOR_IMPLEMENTATION.xdc
# 原虚拟clock+zero-delay未被CDC分类器展开。仅在分析视图中给实际BCLK源管脚
# 建立参考，输入延迟也仅用于拓扑分类；绝不用于真实STA或导出。
create_clock -name codec_bclk_ANALYSIS_ONLY -period 651.042 [get_ports wm8960_bclk]
set_input_delay -clock codec_bclk_ANALYSIS_ONLY -max 10.000 [get_ports {wm8960_lrclk wm8960_adcdat}]
set_input_delay -clock codec_bclk_ANALYSIS_ONLY -min 0.000 [get_ports {wm8960_lrclk wm8960_adcdat}]
foreach {port stem} {wm8960_bclk bclk wm8960_lrclk lrclk wm8960_adcdat adc} {
    set first [get_cells -hier -regexp [format {.*sampler/.*reg_%s_sync_reg\[0\]$} $stem]]
    if {[llength $first] != 1} {error "Missing unique first stage for $port"}
    set destination [get_pins -of_objects $first -filter {REF_PIN_NAME == D}]
    set_false_path -from [get_ports $port] -to $destination
}
report_cdc -details -all_checks_per_endpoint -no_waiver -file reports/cdc_topology_view_only.rpt
write_xdc -force reports/CDC_TOPOLOGY_VIEW_ONLY_NOT_FOR_IMPLEMENTATION.xdc
puts "A13_POSTCHECK_ONLY_NO_EXPORT_NO_BOARD"
