# Additional read-only inspection; never modify a06 or any XDC exceptions.
if {[version -short] ne "2026.1"} {error "2026.1 required"}
set_param general.maxThreads 2
open_checkpoint ./a06_routed.dcp
if {[get_property PART [current_design]] ne "xck26-sfvc784-2LV-c"} {error "part mismatch"}
file mkdir reports
report_bus_skew -file reports/bus_skew.rpt
set fp [open reports/config_source_cells.txt w]
foreach cell [lsort [get_cells -hier -quiet -filter {NAME =~ *rChannelMux_01_reg* || NAME =~ *fs_multiplier_value_reg*}]] {
    puts $fp "CELL $cell REF [get_property REF_NAME $cell] INIT [get_property INIT $cell]"
    foreach suffix {R S CE D} {
        set pin [get_pins -quiet $cell/$suffix]
        if {[llength $pin]} {puts $fp "$suffix NET [get_nets -quiet -of_objects $pin]"}
    }
}
close $fp
close_design
puts "READ_ONLY_BUS_SKEW_CONFIG_SOURCE_COMPLETE_NO_BOARD"
