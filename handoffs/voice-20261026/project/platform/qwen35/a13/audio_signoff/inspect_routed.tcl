# Read-only analysis of a private copy of a06. No timing-exception changes.
if {[version -short] ne "2026.1"} {error "2026.1 required"}
set_param general.maxThreads 2
open_checkpoint ./a06_routed.dcp
if {[get_property PART [current_design]] ne "xck26-sfvc784-2LV-c"} {error "part mismatch"}
file mkdir reports
report_cdc -details -file reports/cdc.rpt
report_timing_summary -check_timing_verbose -file reports/timing.rpt
report_methodology -file reports/methodology.rpt
report_io -file reports/io.rpt
set fp [open reports/cdc_cells.txt w]
foreach pattern {*xpm_cdc_array_multiplier* *CDC_CHMUX_INST*} {
    puts $fp "PATTERN $pattern"
    foreach cell [lsort [get_cells -hier -quiet -filter "NAME =~ $pattern"]] {
        if {[get_property IS_SEQUENTIAL $cell]} {
            puts $fp "CELL $cell REF [get_property REF_NAME $cell]"
            foreach prop {INIT ASYNC_REG} {
                if {[lsearch -exact [list_property $cell] $prop] >= 0} {puts $fp "$prop [get_property $prop $cell]"}
            }
            set dp [get_pins -quiet $cell/D]
            if {[llength $dp]} {
                puts $fp "STARTPOINTS [all_fanin -to $dp -flat -startpoints_only]"
            }
        }
    }
}
close $fp
# Delay type min_max reports actual existing paths. It does NOT constrain the
# asynchronous IIC inputs to the PS clock or certify off-board analog edges.
foreach port {wm8960_iic_sda_io wm8960_iic_scl_io} {
    report_timing -from [get_ports $port] -delay_type min_max -max_paths 4 -path_type full_clock_expanded -file reports/${port}_input.rpt
    report_timing -to [get_ports $port] -delay_type min_max -max_paths 4 -path_type full_clock_expanded -file reports/${port}_output.rpt
}
set fp [open reports/iic_cells.txt w]
foreach cell [lsort [get_cells -hier -quiet -filter {NAME =~ *iic* && (REF_NAME == IOBUF || ASYNC_REG == TRUE)}]] {
    puts $fp "CELL $cell REF [get_property REF_NAME $cell]"
    foreach pin [get_pins -quiet $cell/*] {
        puts $fp "PIN $pin DIR [get_property DIRECTION $pin] NET [get_nets -quiet -of_objects $pin]"
    }
}
close $fp
close_design
puts "READ_ONLY_A06_INSPECTION_COMPLETE_NO_CONSTRAINT_CHANGES_NO_BOARD"
