# 仅失败静态门禁后的功能诊断，不是交付批准；无hw_manager或板端操作。
if {[version -short] ne "2026.1"} {error "2026.1 required"}
set bin D:/AMDDesignTools/2026.1/Vivado/bin
puts [exec $bin/xvlog.bat inputs/rtl/audio_input_sampler.v inputs/rtl/audio_serial_slave.v inputs/tb/tb_audio_serial_slave.v 2>@1]
puts [exec $bin/xelab.bat tb_audio_serial_slave -s audio_serial_sim --debug typical 2>@1]
set result [exec $bin/xsim.bat audio_serial_sim -runall -onfinish quit 2>@1]
puts $result
if {![string match {*VERILOG-GEN-RESULT PASS*} $result]} {error "self-check did not pass"}
puts "A13_DIAGNOSTIC_SIMULATION_PASSED_NOT_STATIC_OR_BOARD_ACCEPTANCE"
