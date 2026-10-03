//==============================================================
//Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
//Tool Version Limit: 2026.06
//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//
//==============================================================

`ifndef SV_MODULE_TOP_SV
`define SV_MODULE_TOP_SV


`timescale 1ns/1ps


`include "uvm_macros.svh"
import uvm_pkg::*;
import file_agent_pkg::*;
import w4a8_linear_v1_subsystem_pkg::*;
`include "w4a8_linear_v1_subsys_test_sequence_lib.sv"
`include "w4a8_linear_v1_test_lib.sv"


module sv_module_top;


    misc_interface              misc_if ( .clock(apatb_w4a8_linear_v1_top.AESL_clock), .reset(apatb_w4a8_linear_v1_top.AESL_reset) );
    assign misc_if.tb2dut_ap_start_kernel = apatb_w4a8_linear_v1_top.AESL_inst_w4a8_linear_v1.ap_start;
    assign misc_if.dut2tb_ap_ready = apatb_w4a8_linear_v1_top.AESL_inst_w4a8_linear_v1.ap_ready;
    assign misc_if.dut2tb_ap_done_kernel = apatb_w4a8_linear_v1_top.AESL_inst_w4a8_linear_v1.ap_done;
    initial begin
        uvm_config_db #(virtual misc_interface)::set(null, "uvm_test_top.top_env.*", "misc_if", misc_if);
    end


    axi_if #(64,16,8,3,1)  axi_gmem_w_if (.clk  (apatb_w4a8_linear_v1_top.AESL_clock), .rst(apatb_w4a8_linear_v1_top.AESL_reset));
    assign axi_gmem_w_if.AWVALID = apatb_w4a8_linear_v1_top.gmem_w_AWVALID;
    assign apatb_w4a8_linear_v1_top.gmem_w_AWREADY = axi_gmem_w_if.AWREADY;
    assign axi_gmem_w_if.AWADDR = apatb_w4a8_linear_v1_top.gmem_w_AWADDR;
    assign axi_gmem_w_if.AWID = apatb_w4a8_linear_v1_top.gmem_w_AWID;
    assign axi_gmem_w_if.AWLEN = apatb_w4a8_linear_v1_top.gmem_w_AWLEN;
    assign axi_gmem_w_if.AWSIZE = apatb_w4a8_linear_v1_top.gmem_w_AWSIZE;
    assign axi_gmem_w_if.AWBURST = apatb_w4a8_linear_v1_top.gmem_w_AWBURST;
    assign axi_gmem_w_if.AWLOCK = apatb_w4a8_linear_v1_top.gmem_w_AWLOCK;
    assign axi_gmem_w_if.AWCACHE = apatb_w4a8_linear_v1_top.gmem_w_AWCACHE;
    assign axi_gmem_w_if.AWPROT = apatb_w4a8_linear_v1_top.gmem_w_AWPROT;
    assign axi_gmem_w_if.AWQOS = apatb_w4a8_linear_v1_top.gmem_w_AWQOS;
    assign axi_gmem_w_if.AWREGION = apatb_w4a8_linear_v1_top.gmem_w_AWREGION;
    assign axi_gmem_w_if.AWUSER = apatb_w4a8_linear_v1_top.gmem_w_AWUSER;
    assign axi_gmem_w_if.WVALID = apatb_w4a8_linear_v1_top.gmem_w_WVALID;
    assign apatb_w4a8_linear_v1_top.gmem_w_WREADY = axi_gmem_w_if.WREADY;
    assign axi_gmem_w_if.WDATA = apatb_w4a8_linear_v1_top.gmem_w_WDATA;
    assign axi_gmem_w_if.WSTRB = apatb_w4a8_linear_v1_top.gmem_w_WSTRB;
    assign axi_gmem_w_if.WLAST = apatb_w4a8_linear_v1_top.gmem_w_WLAST;
    assign axi_gmem_w_if.WID = apatb_w4a8_linear_v1_top.gmem_w_WID;
    assign axi_gmem_w_if.WUSER = apatb_w4a8_linear_v1_top.gmem_w_WUSER;
    assign axi_gmem_w_if.ARVALID = apatb_w4a8_linear_v1_top.gmem_w_ARVALID;
    assign apatb_w4a8_linear_v1_top.gmem_w_ARREADY = axi_gmem_w_if.ARREADY;
    assign axi_gmem_w_if.ARADDR = apatb_w4a8_linear_v1_top.gmem_w_ARADDR;
    assign axi_gmem_w_if.ARID = apatb_w4a8_linear_v1_top.gmem_w_ARID;
    assign axi_gmem_w_if.ARLEN = apatb_w4a8_linear_v1_top.gmem_w_ARLEN;
    assign axi_gmem_w_if.ARSIZE = apatb_w4a8_linear_v1_top.gmem_w_ARSIZE;
    assign axi_gmem_w_if.ARBURST = apatb_w4a8_linear_v1_top.gmem_w_ARBURST;
    assign axi_gmem_w_if.ARLOCK = apatb_w4a8_linear_v1_top.gmem_w_ARLOCK;
    assign axi_gmem_w_if.ARCACHE = apatb_w4a8_linear_v1_top.gmem_w_ARCACHE;
    assign axi_gmem_w_if.ARPROT = apatb_w4a8_linear_v1_top.gmem_w_ARPROT;
    assign axi_gmem_w_if.ARQOS = apatb_w4a8_linear_v1_top.gmem_w_ARQOS;
    assign axi_gmem_w_if.ARREGION = apatb_w4a8_linear_v1_top.gmem_w_ARREGION;
    assign axi_gmem_w_if.ARUSER = apatb_w4a8_linear_v1_top.gmem_w_ARUSER;
    assign apatb_w4a8_linear_v1_top.gmem_w_RVALID = axi_gmem_w_if.RVALID;
    assign axi_gmem_w_if.RREADY = apatb_w4a8_linear_v1_top.gmem_w_RREADY;
    assign apatb_w4a8_linear_v1_top.gmem_w_RDATA = axi_gmem_w_if.RDATA;
    assign apatb_w4a8_linear_v1_top.gmem_w_RLAST = axi_gmem_w_if.RLAST;
    assign apatb_w4a8_linear_v1_top.gmem_w_RID = axi_gmem_w_if.RID;
    assign apatb_w4a8_linear_v1_top.gmem_w_RUSER = axi_gmem_w_if.RUSER;
    assign apatb_w4a8_linear_v1_top.gmem_w_RRESP = axi_gmem_w_if.RRESP;
    assign apatb_w4a8_linear_v1_top.gmem_w_BVALID = axi_gmem_w_if.BVALID;
    assign axi_gmem_w_if.BREADY = apatb_w4a8_linear_v1_top.gmem_w_BREADY;
    assign apatb_w4a8_linear_v1_top.gmem_w_BRESP = axi_gmem_w_if.BRESP;
    assign apatb_w4a8_linear_v1_top.gmem_w_BID = axi_gmem_w_if.BID;
    assign apatb_w4a8_linear_v1_top.gmem_w_BUSER = axi_gmem_w_if.BUSER;
    initial begin
        uvm_config_db #( virtual axi_if#(64,16,8,3,1) )::set(null, "uvm_test_top.top_env.axi_master_gmem_w.*", "vif", axi_gmem_w_if);
    end


    axi_if #(64,4,8,3,1)  axi_gmem_sw_if (.clk  (apatb_w4a8_linear_v1_top.AESL_clock), .rst(apatb_w4a8_linear_v1_top.AESL_reset));
    assign axi_gmem_sw_if.AWVALID = apatb_w4a8_linear_v1_top.gmem_sw_AWVALID;
    assign apatb_w4a8_linear_v1_top.gmem_sw_AWREADY = axi_gmem_sw_if.AWREADY;
    assign axi_gmem_sw_if.AWADDR = apatb_w4a8_linear_v1_top.gmem_sw_AWADDR;
    assign axi_gmem_sw_if.AWID = apatb_w4a8_linear_v1_top.gmem_sw_AWID;
    assign axi_gmem_sw_if.AWLEN = apatb_w4a8_linear_v1_top.gmem_sw_AWLEN;
    assign axi_gmem_sw_if.AWSIZE = apatb_w4a8_linear_v1_top.gmem_sw_AWSIZE;
    assign axi_gmem_sw_if.AWBURST = apatb_w4a8_linear_v1_top.gmem_sw_AWBURST;
    assign axi_gmem_sw_if.AWLOCK = apatb_w4a8_linear_v1_top.gmem_sw_AWLOCK;
    assign axi_gmem_sw_if.AWCACHE = apatb_w4a8_linear_v1_top.gmem_sw_AWCACHE;
    assign axi_gmem_sw_if.AWPROT = apatb_w4a8_linear_v1_top.gmem_sw_AWPROT;
    assign axi_gmem_sw_if.AWQOS = apatb_w4a8_linear_v1_top.gmem_sw_AWQOS;
    assign axi_gmem_sw_if.AWREGION = apatb_w4a8_linear_v1_top.gmem_sw_AWREGION;
    assign axi_gmem_sw_if.AWUSER = apatb_w4a8_linear_v1_top.gmem_sw_AWUSER;
    assign axi_gmem_sw_if.WVALID = apatb_w4a8_linear_v1_top.gmem_sw_WVALID;
    assign apatb_w4a8_linear_v1_top.gmem_sw_WREADY = axi_gmem_sw_if.WREADY;
    assign axi_gmem_sw_if.WDATA = apatb_w4a8_linear_v1_top.gmem_sw_WDATA;
    assign axi_gmem_sw_if.WSTRB = apatb_w4a8_linear_v1_top.gmem_sw_WSTRB;
    assign axi_gmem_sw_if.WLAST = apatb_w4a8_linear_v1_top.gmem_sw_WLAST;
    assign axi_gmem_sw_if.WID = apatb_w4a8_linear_v1_top.gmem_sw_WID;
    assign axi_gmem_sw_if.WUSER = apatb_w4a8_linear_v1_top.gmem_sw_WUSER;
    assign axi_gmem_sw_if.ARVALID = apatb_w4a8_linear_v1_top.gmem_sw_ARVALID;
    assign apatb_w4a8_linear_v1_top.gmem_sw_ARREADY = axi_gmem_sw_if.ARREADY;
    assign axi_gmem_sw_if.ARADDR = apatb_w4a8_linear_v1_top.gmem_sw_ARADDR;
    assign axi_gmem_sw_if.ARID = apatb_w4a8_linear_v1_top.gmem_sw_ARID;
    assign axi_gmem_sw_if.ARLEN = apatb_w4a8_linear_v1_top.gmem_sw_ARLEN;
    assign axi_gmem_sw_if.ARSIZE = apatb_w4a8_linear_v1_top.gmem_sw_ARSIZE;
    assign axi_gmem_sw_if.ARBURST = apatb_w4a8_linear_v1_top.gmem_sw_ARBURST;
    assign axi_gmem_sw_if.ARLOCK = apatb_w4a8_linear_v1_top.gmem_sw_ARLOCK;
    assign axi_gmem_sw_if.ARCACHE = apatb_w4a8_linear_v1_top.gmem_sw_ARCACHE;
    assign axi_gmem_sw_if.ARPROT = apatb_w4a8_linear_v1_top.gmem_sw_ARPROT;
    assign axi_gmem_sw_if.ARQOS = apatb_w4a8_linear_v1_top.gmem_sw_ARQOS;
    assign axi_gmem_sw_if.ARREGION = apatb_w4a8_linear_v1_top.gmem_sw_ARREGION;
    assign axi_gmem_sw_if.ARUSER = apatb_w4a8_linear_v1_top.gmem_sw_ARUSER;
    assign apatb_w4a8_linear_v1_top.gmem_sw_RVALID = axi_gmem_sw_if.RVALID;
    assign axi_gmem_sw_if.RREADY = apatb_w4a8_linear_v1_top.gmem_sw_RREADY;
    assign apatb_w4a8_linear_v1_top.gmem_sw_RDATA = axi_gmem_sw_if.RDATA;
    assign apatb_w4a8_linear_v1_top.gmem_sw_RLAST = axi_gmem_sw_if.RLAST;
    assign apatb_w4a8_linear_v1_top.gmem_sw_RID = axi_gmem_sw_if.RID;
    assign apatb_w4a8_linear_v1_top.gmem_sw_RUSER = axi_gmem_sw_if.RUSER;
    assign apatb_w4a8_linear_v1_top.gmem_sw_RRESP = axi_gmem_sw_if.RRESP;
    assign apatb_w4a8_linear_v1_top.gmem_sw_BVALID = axi_gmem_sw_if.BVALID;
    assign axi_gmem_sw_if.BREADY = apatb_w4a8_linear_v1_top.gmem_sw_BREADY;
    assign apatb_w4a8_linear_v1_top.gmem_sw_BRESP = axi_gmem_sw_if.BRESP;
    assign apatb_w4a8_linear_v1_top.gmem_sw_BID = axi_gmem_sw_if.BID;
    assign apatb_w4a8_linear_v1_top.gmem_sw_BUSER = axi_gmem_sw_if.BUSER;
    initial begin
        uvm_config_db #( virtual axi_if#(64,4,8,3,1) )::set(null, "uvm_test_top.top_env.axi_master_gmem_sw.*", "vif", axi_gmem_sw_if);
    end


    axi_if #(64,16,8,3,1)  axi_gmem_x_if (.clk  (apatb_w4a8_linear_v1_top.AESL_clock), .rst(apatb_w4a8_linear_v1_top.AESL_reset));
    assign axi_gmem_x_if.AWVALID = apatb_w4a8_linear_v1_top.gmem_x_AWVALID;
    assign apatb_w4a8_linear_v1_top.gmem_x_AWREADY = axi_gmem_x_if.AWREADY;
    assign axi_gmem_x_if.AWADDR = apatb_w4a8_linear_v1_top.gmem_x_AWADDR;
    assign axi_gmem_x_if.AWID = apatb_w4a8_linear_v1_top.gmem_x_AWID;
    assign axi_gmem_x_if.AWLEN = apatb_w4a8_linear_v1_top.gmem_x_AWLEN;
    assign axi_gmem_x_if.AWSIZE = apatb_w4a8_linear_v1_top.gmem_x_AWSIZE;
    assign axi_gmem_x_if.AWBURST = apatb_w4a8_linear_v1_top.gmem_x_AWBURST;
    assign axi_gmem_x_if.AWLOCK = apatb_w4a8_linear_v1_top.gmem_x_AWLOCK;
    assign axi_gmem_x_if.AWCACHE = apatb_w4a8_linear_v1_top.gmem_x_AWCACHE;
    assign axi_gmem_x_if.AWPROT = apatb_w4a8_linear_v1_top.gmem_x_AWPROT;
    assign axi_gmem_x_if.AWQOS = apatb_w4a8_linear_v1_top.gmem_x_AWQOS;
    assign axi_gmem_x_if.AWREGION = apatb_w4a8_linear_v1_top.gmem_x_AWREGION;
    assign axi_gmem_x_if.AWUSER = apatb_w4a8_linear_v1_top.gmem_x_AWUSER;
    assign axi_gmem_x_if.WVALID = apatb_w4a8_linear_v1_top.gmem_x_WVALID;
    assign apatb_w4a8_linear_v1_top.gmem_x_WREADY = axi_gmem_x_if.WREADY;
    assign axi_gmem_x_if.WDATA = apatb_w4a8_linear_v1_top.gmem_x_WDATA;
    assign axi_gmem_x_if.WSTRB = apatb_w4a8_linear_v1_top.gmem_x_WSTRB;
    assign axi_gmem_x_if.WLAST = apatb_w4a8_linear_v1_top.gmem_x_WLAST;
    assign axi_gmem_x_if.WID = apatb_w4a8_linear_v1_top.gmem_x_WID;
    assign axi_gmem_x_if.WUSER = apatb_w4a8_linear_v1_top.gmem_x_WUSER;
    assign axi_gmem_x_if.ARVALID = apatb_w4a8_linear_v1_top.gmem_x_ARVALID;
    assign apatb_w4a8_linear_v1_top.gmem_x_ARREADY = axi_gmem_x_if.ARREADY;
    assign axi_gmem_x_if.ARADDR = apatb_w4a8_linear_v1_top.gmem_x_ARADDR;
    assign axi_gmem_x_if.ARID = apatb_w4a8_linear_v1_top.gmem_x_ARID;
    assign axi_gmem_x_if.ARLEN = apatb_w4a8_linear_v1_top.gmem_x_ARLEN;
    assign axi_gmem_x_if.ARSIZE = apatb_w4a8_linear_v1_top.gmem_x_ARSIZE;
    assign axi_gmem_x_if.ARBURST = apatb_w4a8_linear_v1_top.gmem_x_ARBURST;
    assign axi_gmem_x_if.ARLOCK = apatb_w4a8_linear_v1_top.gmem_x_ARLOCK;
    assign axi_gmem_x_if.ARCACHE = apatb_w4a8_linear_v1_top.gmem_x_ARCACHE;
    assign axi_gmem_x_if.ARPROT = apatb_w4a8_linear_v1_top.gmem_x_ARPROT;
    assign axi_gmem_x_if.ARQOS = apatb_w4a8_linear_v1_top.gmem_x_ARQOS;
    assign axi_gmem_x_if.ARREGION = apatb_w4a8_linear_v1_top.gmem_x_ARREGION;
    assign axi_gmem_x_if.ARUSER = apatb_w4a8_linear_v1_top.gmem_x_ARUSER;
    assign apatb_w4a8_linear_v1_top.gmem_x_RVALID = axi_gmem_x_if.RVALID;
    assign axi_gmem_x_if.RREADY = apatb_w4a8_linear_v1_top.gmem_x_RREADY;
    assign apatb_w4a8_linear_v1_top.gmem_x_RDATA = axi_gmem_x_if.RDATA;
    assign apatb_w4a8_linear_v1_top.gmem_x_RLAST = axi_gmem_x_if.RLAST;
    assign apatb_w4a8_linear_v1_top.gmem_x_RID = axi_gmem_x_if.RID;
    assign apatb_w4a8_linear_v1_top.gmem_x_RUSER = axi_gmem_x_if.RUSER;
    assign apatb_w4a8_linear_v1_top.gmem_x_RRESP = axi_gmem_x_if.RRESP;
    assign apatb_w4a8_linear_v1_top.gmem_x_BVALID = axi_gmem_x_if.BVALID;
    assign axi_gmem_x_if.BREADY = apatb_w4a8_linear_v1_top.gmem_x_BREADY;
    assign apatb_w4a8_linear_v1_top.gmem_x_BRESP = axi_gmem_x_if.BRESP;
    assign apatb_w4a8_linear_v1_top.gmem_x_BID = axi_gmem_x_if.BID;
    assign apatb_w4a8_linear_v1_top.gmem_x_BUSER = axi_gmem_x_if.BUSER;
    initial begin
        uvm_config_db #( virtual axi_if#(64,16,8,3,1) )::set(null, "uvm_test_top.top_env.axi_master_gmem_x.*", "vif", axi_gmem_x_if);
    end


    axi_if #(64,4,8,3,1)  axi_gmem_y_if (.clk  (apatb_w4a8_linear_v1_top.AESL_clock), .rst(apatb_w4a8_linear_v1_top.AESL_reset));
    assign axi_gmem_y_if.AWVALID = apatb_w4a8_linear_v1_top.gmem_y_AWVALID;
    assign apatb_w4a8_linear_v1_top.gmem_y_AWREADY = axi_gmem_y_if.AWREADY;
    assign axi_gmem_y_if.AWADDR = apatb_w4a8_linear_v1_top.gmem_y_AWADDR;
    assign axi_gmem_y_if.AWID = apatb_w4a8_linear_v1_top.gmem_y_AWID;
    assign axi_gmem_y_if.AWLEN = apatb_w4a8_linear_v1_top.gmem_y_AWLEN;
    assign axi_gmem_y_if.AWSIZE = apatb_w4a8_linear_v1_top.gmem_y_AWSIZE;
    assign axi_gmem_y_if.AWBURST = apatb_w4a8_linear_v1_top.gmem_y_AWBURST;
    assign axi_gmem_y_if.AWLOCK = apatb_w4a8_linear_v1_top.gmem_y_AWLOCK;
    assign axi_gmem_y_if.AWCACHE = apatb_w4a8_linear_v1_top.gmem_y_AWCACHE;
    assign axi_gmem_y_if.AWPROT = apatb_w4a8_linear_v1_top.gmem_y_AWPROT;
    assign axi_gmem_y_if.AWQOS = apatb_w4a8_linear_v1_top.gmem_y_AWQOS;
    assign axi_gmem_y_if.AWREGION = apatb_w4a8_linear_v1_top.gmem_y_AWREGION;
    assign axi_gmem_y_if.AWUSER = apatb_w4a8_linear_v1_top.gmem_y_AWUSER;
    assign axi_gmem_y_if.WVALID = apatb_w4a8_linear_v1_top.gmem_y_WVALID;
    assign apatb_w4a8_linear_v1_top.gmem_y_WREADY = axi_gmem_y_if.WREADY;
    assign axi_gmem_y_if.WDATA = apatb_w4a8_linear_v1_top.gmem_y_WDATA;
    assign axi_gmem_y_if.WSTRB = apatb_w4a8_linear_v1_top.gmem_y_WSTRB;
    assign axi_gmem_y_if.WLAST = apatb_w4a8_linear_v1_top.gmem_y_WLAST;
    assign axi_gmem_y_if.WID = apatb_w4a8_linear_v1_top.gmem_y_WID;
    assign axi_gmem_y_if.WUSER = apatb_w4a8_linear_v1_top.gmem_y_WUSER;
    assign axi_gmem_y_if.ARVALID = apatb_w4a8_linear_v1_top.gmem_y_ARVALID;
    assign apatb_w4a8_linear_v1_top.gmem_y_ARREADY = axi_gmem_y_if.ARREADY;
    assign axi_gmem_y_if.ARADDR = apatb_w4a8_linear_v1_top.gmem_y_ARADDR;
    assign axi_gmem_y_if.ARID = apatb_w4a8_linear_v1_top.gmem_y_ARID;
    assign axi_gmem_y_if.ARLEN = apatb_w4a8_linear_v1_top.gmem_y_ARLEN;
    assign axi_gmem_y_if.ARSIZE = apatb_w4a8_linear_v1_top.gmem_y_ARSIZE;
    assign axi_gmem_y_if.ARBURST = apatb_w4a8_linear_v1_top.gmem_y_ARBURST;
    assign axi_gmem_y_if.ARLOCK = apatb_w4a8_linear_v1_top.gmem_y_ARLOCK;
    assign axi_gmem_y_if.ARCACHE = apatb_w4a8_linear_v1_top.gmem_y_ARCACHE;
    assign axi_gmem_y_if.ARPROT = apatb_w4a8_linear_v1_top.gmem_y_ARPROT;
    assign axi_gmem_y_if.ARQOS = apatb_w4a8_linear_v1_top.gmem_y_ARQOS;
    assign axi_gmem_y_if.ARREGION = apatb_w4a8_linear_v1_top.gmem_y_ARREGION;
    assign axi_gmem_y_if.ARUSER = apatb_w4a8_linear_v1_top.gmem_y_ARUSER;
    assign apatb_w4a8_linear_v1_top.gmem_y_RVALID = axi_gmem_y_if.RVALID;
    assign axi_gmem_y_if.RREADY = apatb_w4a8_linear_v1_top.gmem_y_RREADY;
    assign apatb_w4a8_linear_v1_top.gmem_y_RDATA = axi_gmem_y_if.RDATA;
    assign apatb_w4a8_linear_v1_top.gmem_y_RLAST = axi_gmem_y_if.RLAST;
    assign apatb_w4a8_linear_v1_top.gmem_y_RID = axi_gmem_y_if.RID;
    assign apatb_w4a8_linear_v1_top.gmem_y_RUSER = axi_gmem_y_if.RUSER;
    assign apatb_w4a8_linear_v1_top.gmem_y_RRESP = axi_gmem_y_if.RRESP;
    assign apatb_w4a8_linear_v1_top.gmem_y_BVALID = axi_gmem_y_if.BVALID;
    assign axi_gmem_y_if.BREADY = apatb_w4a8_linear_v1_top.gmem_y_BREADY;
    assign apatb_w4a8_linear_v1_top.gmem_y_BRESP = axi_gmem_y_if.BRESP;
    assign apatb_w4a8_linear_v1_top.gmem_y_BID = axi_gmem_y_if.BID;
    assign apatb_w4a8_linear_v1_top.gmem_y_BUSER = axi_gmem_y_if.BUSER;
    initial begin
        uvm_config_db #( virtual axi_if#(64,4,8,3,1) )::set(null, "uvm_test_top.top_env.axi_master_gmem_y.*", "vif", axi_gmem_y_if);
    end


    axi_if #(64,64,8,3,1)  axi_gmem_meta_if (.clk  (apatb_w4a8_linear_v1_top.AESL_clock), .rst(apatb_w4a8_linear_v1_top.AESL_reset));
    assign axi_gmem_meta_if.AWVALID = apatb_w4a8_linear_v1_top.gmem_meta_AWVALID;
    assign apatb_w4a8_linear_v1_top.gmem_meta_AWREADY = axi_gmem_meta_if.AWREADY;
    assign axi_gmem_meta_if.AWADDR = apatb_w4a8_linear_v1_top.gmem_meta_AWADDR;
    assign axi_gmem_meta_if.AWID = apatb_w4a8_linear_v1_top.gmem_meta_AWID;
    assign axi_gmem_meta_if.AWLEN = apatb_w4a8_linear_v1_top.gmem_meta_AWLEN;
    assign axi_gmem_meta_if.AWSIZE = apatb_w4a8_linear_v1_top.gmem_meta_AWSIZE;
    assign axi_gmem_meta_if.AWBURST = apatb_w4a8_linear_v1_top.gmem_meta_AWBURST;
    assign axi_gmem_meta_if.AWLOCK = apatb_w4a8_linear_v1_top.gmem_meta_AWLOCK;
    assign axi_gmem_meta_if.AWCACHE = apatb_w4a8_linear_v1_top.gmem_meta_AWCACHE;
    assign axi_gmem_meta_if.AWPROT = apatb_w4a8_linear_v1_top.gmem_meta_AWPROT;
    assign axi_gmem_meta_if.AWQOS = apatb_w4a8_linear_v1_top.gmem_meta_AWQOS;
    assign axi_gmem_meta_if.AWREGION = apatb_w4a8_linear_v1_top.gmem_meta_AWREGION;
    assign axi_gmem_meta_if.AWUSER = apatb_w4a8_linear_v1_top.gmem_meta_AWUSER;
    assign axi_gmem_meta_if.WVALID = apatb_w4a8_linear_v1_top.gmem_meta_WVALID;
    assign apatb_w4a8_linear_v1_top.gmem_meta_WREADY = axi_gmem_meta_if.WREADY;
    assign axi_gmem_meta_if.WDATA = apatb_w4a8_linear_v1_top.gmem_meta_WDATA;
    assign axi_gmem_meta_if.WSTRB = apatb_w4a8_linear_v1_top.gmem_meta_WSTRB;
    assign axi_gmem_meta_if.WLAST = apatb_w4a8_linear_v1_top.gmem_meta_WLAST;
    assign axi_gmem_meta_if.WID = apatb_w4a8_linear_v1_top.gmem_meta_WID;
    assign axi_gmem_meta_if.WUSER = apatb_w4a8_linear_v1_top.gmem_meta_WUSER;
    assign axi_gmem_meta_if.ARVALID = apatb_w4a8_linear_v1_top.gmem_meta_ARVALID;
    assign apatb_w4a8_linear_v1_top.gmem_meta_ARREADY = axi_gmem_meta_if.ARREADY;
    assign axi_gmem_meta_if.ARADDR = apatb_w4a8_linear_v1_top.gmem_meta_ARADDR;
    assign axi_gmem_meta_if.ARID = apatb_w4a8_linear_v1_top.gmem_meta_ARID;
    assign axi_gmem_meta_if.ARLEN = apatb_w4a8_linear_v1_top.gmem_meta_ARLEN;
    assign axi_gmem_meta_if.ARSIZE = apatb_w4a8_linear_v1_top.gmem_meta_ARSIZE;
    assign axi_gmem_meta_if.ARBURST = apatb_w4a8_linear_v1_top.gmem_meta_ARBURST;
    assign axi_gmem_meta_if.ARLOCK = apatb_w4a8_linear_v1_top.gmem_meta_ARLOCK;
    assign axi_gmem_meta_if.ARCACHE = apatb_w4a8_linear_v1_top.gmem_meta_ARCACHE;
    assign axi_gmem_meta_if.ARPROT = apatb_w4a8_linear_v1_top.gmem_meta_ARPROT;
    assign axi_gmem_meta_if.ARQOS = apatb_w4a8_linear_v1_top.gmem_meta_ARQOS;
    assign axi_gmem_meta_if.ARREGION = apatb_w4a8_linear_v1_top.gmem_meta_ARREGION;
    assign axi_gmem_meta_if.ARUSER = apatb_w4a8_linear_v1_top.gmem_meta_ARUSER;
    assign apatb_w4a8_linear_v1_top.gmem_meta_RVALID = axi_gmem_meta_if.RVALID;
    assign axi_gmem_meta_if.RREADY = apatb_w4a8_linear_v1_top.gmem_meta_RREADY;
    assign apatb_w4a8_linear_v1_top.gmem_meta_RDATA = axi_gmem_meta_if.RDATA;
    assign apatb_w4a8_linear_v1_top.gmem_meta_RLAST = axi_gmem_meta_if.RLAST;
    assign apatb_w4a8_linear_v1_top.gmem_meta_RID = axi_gmem_meta_if.RID;
    assign apatb_w4a8_linear_v1_top.gmem_meta_RUSER = axi_gmem_meta_if.RUSER;
    assign apatb_w4a8_linear_v1_top.gmem_meta_RRESP = axi_gmem_meta_if.RRESP;
    assign apatb_w4a8_linear_v1_top.gmem_meta_BVALID = axi_gmem_meta_if.BVALID;
    assign axi_gmem_meta_if.BREADY = apatb_w4a8_linear_v1_top.gmem_meta_BREADY;
    assign apatb_w4a8_linear_v1_top.gmem_meta_BRESP = axi_gmem_meta_if.BRESP;
    assign apatb_w4a8_linear_v1_top.gmem_meta_BID = axi_gmem_meta_if.BID;
    assign apatb_w4a8_linear_v1_top.gmem_meta_BUSER = axi_gmem_meta_if.BUSER;
    initial begin
        uvm_config_db #( virtual axi_if#(64,64,8,3,1) )::set(null, "uvm_test_top.top_env.axi_master_gmem_meta.*", "vif", axi_gmem_meta_if);
    end


    axi_if #(8,4,4,3,1)  axi_control_if (.clk  (apatb_w4a8_linear_v1_top.AESL_clock), .rst(apatb_w4a8_linear_v1_top.AESL_reset));
    assign apatb_w4a8_linear_v1_top.control_AWADDR = axi_control_if.AWADDR;
    assign apatb_w4a8_linear_v1_top.control_AWVALID = axi_control_if.AWVALID;
    assign axi_control_if.AWREADY = apatb_w4a8_linear_v1_top.control_AWREADY;
    assign apatb_w4a8_linear_v1_top.control_WVALID = axi_control_if.WVALID;
    assign axi_control_if.WREADY = apatb_w4a8_linear_v1_top.control_WREADY;
    assign apatb_w4a8_linear_v1_top.control_WDATA = axi_control_if.WDATA;
    assign apatb_w4a8_linear_v1_top.control_WSTRB = axi_control_if.WSTRB;
    assign apatb_w4a8_linear_v1_top.control_ARADDR = axi_control_if.ARADDR;
    assign apatb_w4a8_linear_v1_top.control_ARVALID = axi_control_if.ARVALID;
    assign axi_control_if.ARREADY = apatb_w4a8_linear_v1_top.control_ARREADY;
    assign axi_control_if.RVALID = apatb_w4a8_linear_v1_top.control_RVALID;
    assign apatb_w4a8_linear_v1_top.control_RREADY = axi_control_if.RREADY;
    assign axi_control_if.RDATA = apatb_w4a8_linear_v1_top.control_RDATA;
    assign axi_control_if.RRESP = apatb_w4a8_linear_v1_top.control_RRESP;
    assign axi_control_if.BVALID = apatb_w4a8_linear_v1_top.control_BVALID;
    assign apatb_w4a8_linear_v1_top.control_BREADY = axi_control_if.BREADY;
    assign axi_control_if.BRESP = apatb_w4a8_linear_v1_top.control_BRESP;
    assign axi_control_if.BID = 0;
    assign axi_control_if.RID = 0;
    assign axi_control_if.RLAST = 1;
    initial begin
        uvm_config_db #( virtual axi_if#(8,4,4,3,1) )::set(null, "uvm_test_top.top_env.axi_lite_control.*", "vif", axi_control_if);
    end


    initial begin
        run_test();
    end
endmodule
`endif
