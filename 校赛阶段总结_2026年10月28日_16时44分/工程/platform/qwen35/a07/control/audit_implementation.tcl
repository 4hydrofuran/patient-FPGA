# Read-only routed implementation audit. No programming, changing constraints or rebuilding.
if {$argc != 2} { error "usage: audit_implementation.tcl routed.dcp new-report-dir" }
set checkpoint [file normalize [lindex $argv 0]]
set out [file normalize [lindex $argv 1]]
if {![file isfile $checkpoint] || [file exists $out]} { error "checkpoint missing or output exists" }
file mkdir $out
set_param general.maxThreads 2
open_checkpoint $checkpoint
if {![string equal -nocase [get_property PART [current_design]] "xck26-sfvc784-2LV-c"]} { error "wrong part" }
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file [file join $out timing.rpt]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_cdc -details -file [file join $out cdc.rpt]
report_methodology -file [file join $out methodology.rpt]
report_utilization -hierarchical -file [file join $out utilization.rpt]
report_clocks -file [file join $out clocks.rpt]
close_design
puts "REPORTS_GENERATED_NOT_AUTOMATIC_PASS"
exit
