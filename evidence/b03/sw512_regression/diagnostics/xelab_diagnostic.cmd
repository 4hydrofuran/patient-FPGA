@echo off
call D:/2026.1/2026.1/Vivado/bin/xelab xil_defaultlib.apatb_w4a8_linear_v1_top xil_defaultlib.glbl -Oenable_linking_all_libraries -prj w4a8_linear_v1.prj -L smartconnect_v1_0 -L axi_protocol_checker_v1_1_12 -L axi_protocol_checker_v1_1_13 -L axis_protocol_checker_v1_1_11 -L axis_protocol_checker_v1_1_12 -L xil_defaultlib -L unisims_ver -L xpm  -L floating_point_v7_1_22 -L floating_point_v7_0_27 --lib "ieee_proposed=./ieee_proposed" -L uvm -relax -i ./svr -i ./axivip -i ./svtb -i ./file_agent -i ./w4a8_linear_v1_subsystem  -s w4a8_linear_v1  -mt off -v 1
exit /b %errorlevel%
