
log_wave [get_objects -filter {type == in_port || type == out_port || type == inout_port || type == port} /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/*]
set designtopgroup [add_wave_group "Design Top Signals"]
set cinoutgroup [add_wave_group "C InOuts" -into $designtopgroup]
set meta_group [add_wave_group meta(axi_master) -into $cinoutgroup]
set rdata_group [add_wave_group "Read Channel" -into $meta_group]
set wdata_group [add_wave_group "Write Channel" -into $meta_group]
set ctrl_group [add_wave_group "Handshakes" -into $meta_group]
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_BUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_BID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_BRESP -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_BREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_BVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_RRESP -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_RUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_RID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_RLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_RDATA -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_RREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_RVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARREGION -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARQOS -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARPROT -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARCACHE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARLOCK -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARBURST -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARSIZE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARLEN -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARADDR -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_ARVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_WUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_WID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_WLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_WSTRB -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_WDATA -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_WREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_WVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWREGION -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWQOS -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWPROT -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWCACHE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWLOCK -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWBURST -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWSIZE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWLEN -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWADDR -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_meta_AWVALID -into $ctrl_group -color #ffff00 -radix hex
set w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group [add_wave_group w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return(axi_slave) -into $cinoutgroup]
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/interrupt -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_BRESP -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_BREADY -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_BVALID -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_RRESP -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_RDATA -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_RREADY -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_RVALID -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_ARREADY -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_ARVALID -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_ARADDR -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_WSTRB -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_WDATA -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_WREADY -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_WVALID -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_AWREADY -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_AWVALID -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/s_axi_control_AWADDR -into $w_packed__sw__xq__sx__y__meta__t__n__k__w_bytes__sw_bytes__x_bytes__sx_bytes__y_bytes__meta_bytes__job_id__abi_version__return_group -radix hex
set coutputgroup [add_wave_group "C Outputs" -into $designtopgroup]
set y_group [add_wave_group y(axi_master) -into $coutputgroup]
set rdata_group [add_wave_group "Read Channel" -into $y_group]
set wdata_group [add_wave_group "Write Channel" -into $y_group]
set ctrl_group [add_wave_group "Handshakes" -into $y_group]
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_BUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_BID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_BRESP -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_BREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_BVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_RRESP -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_RUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_RID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_RLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_RDATA -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_RREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_RVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARREGION -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARQOS -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARPROT -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARCACHE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARLOCK -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARBURST -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARSIZE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARLEN -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARADDR -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_ARVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_WUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_WID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_WLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_WSTRB -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_WDATA -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_WREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_WVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWREGION -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWQOS -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWPROT -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWCACHE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWLOCK -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWBURST -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWSIZE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWLEN -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWADDR -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_y_AWVALID -into $ctrl_group -color #ffff00 -radix hex
set cinputgroup [add_wave_group "C Inputs" -into $designtopgroup]
set xq__sx_group [add_wave_group xq__sx(axi_master) -into $cinputgroup]
set rdata_group [add_wave_group "Read Channel" -into $xq__sx_group]
set wdata_group [add_wave_group "Write Channel" -into $xq__sx_group]
set ctrl_group [add_wave_group "Handshakes" -into $xq__sx_group]
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_BUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_BID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_BRESP -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_BREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_BVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_RRESP -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_RUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_RID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_RLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_RDATA -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_RREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_RVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARREGION -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARQOS -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARPROT -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARCACHE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARLOCK -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARBURST -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARSIZE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARLEN -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARADDR -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_ARVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_WUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_WID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_WLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_WSTRB -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_WDATA -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_WREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_WVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWREGION -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWQOS -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWPROT -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWCACHE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWLOCK -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWBURST -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWSIZE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWLEN -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWADDR -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_x_AWVALID -into $ctrl_group -color #ffff00 -radix hex
set sw_group [add_wave_group sw(axi_master) -into $cinputgroup]
set rdata_group [add_wave_group "Read Channel" -into $sw_group]
set wdata_group [add_wave_group "Write Channel" -into $sw_group]
set ctrl_group [add_wave_group "Handshakes" -into $sw_group]
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_BUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_BID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_BRESP -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_BREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_BVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_RRESP -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_RUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_RID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_RLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_RDATA -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_RREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_RVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARREGION -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARQOS -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARPROT -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARCACHE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARLOCK -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARBURST -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARSIZE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARLEN -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARADDR -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_ARVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_WUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_WID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_WLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_WSTRB -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_WDATA -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_WREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_WVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWREGION -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWQOS -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWPROT -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWCACHE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWLOCK -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWBURST -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWSIZE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWLEN -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWADDR -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_sw_AWVALID -into $ctrl_group -color #ffff00 -radix hex
set w_packed_group [add_wave_group w_packed(axi_master) -into $cinputgroup]
set rdata_group [add_wave_group "Read Channel" -into $w_packed_group]
set wdata_group [add_wave_group "Write Channel" -into $w_packed_group]
set ctrl_group [add_wave_group "Handshakes" -into $w_packed_group]
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_BUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_BID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_BRESP -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_BREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_BVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_RRESP -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_RUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_RID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_RLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_RDATA -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_RREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_RVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARUSER -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARREGION -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARQOS -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARPROT -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARCACHE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARLOCK -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARBURST -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARSIZE -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARLEN -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARID -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARADDR -into $rdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_ARVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_WUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_WID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_WLAST -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_WSTRB -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_WDATA -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_WREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_WVALID -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWUSER -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWREGION -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWQOS -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWPROT -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWCACHE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWLOCK -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWBURST -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWSIZE -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWLEN -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWID -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWADDR -into $wdata_group -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWREADY -into $ctrl_group -color #ffff00 -radix hex
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/m_axi_gmem_w_AWVALID -into $ctrl_group -color #ffff00 -radix hex
set resetgroup [add_wave_group "Reset" -into $designtopgroup]
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/ap_rst_n -into $resetgroup
set clockgroup [add_wave_group "Clock" -into $designtopgroup]
add_wave /apatb_w4a8_linear_v1_top/AESL_inst_w4a8_linear_v1/ap_clk -into $clockgroup
save_wave_config w4a8_linear_v1.wcfg
run all
quit

