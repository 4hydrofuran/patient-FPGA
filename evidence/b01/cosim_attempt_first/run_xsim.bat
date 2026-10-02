
set PATH=
call D:/2026.1/2026.1/Vivado/bin/xelab xil_defaultlib.apatb_w4a8_linear_v1_top xil_defaultlib.glbl -Oenable_linking_all_libraries -prj w4a8_linear_v1.prj -L smartconnect_v1_0 -L axi_protocol_checker_v1_1_12 -L axi_protocol_checker_v1_1_13 -L axis_protocol_checker_v1_1_11 -L axis_protocol_checker_v1_1_12 -L xil_defaultlib -L unisims_ver -L xpm  -L floating_point_v7_1_22 -L floating_point_v7_0_27 --lib "ieee_proposed=./ieee_proposed" -L uvm -relax -i ./svr -i ./axivip -i ./svtb -i ./file_agent -i ./w4a8_linear_v1_subsystem  -s w4a8_linear_v1 
call D:/2026.1/2026.1/Vivado/bin/xsim -testplusarg "UVM_VERBOSITY=UVM_NONE" -testplusarg "UVM_TESTNAME=w4a8_linear_v1_test_lib" -testplusarg "UVM_TIMEOUT=20000000000000" --noieeewarnings w4a8_linear_v1 -tclbatch w4a8_linear_v1.tcl 

