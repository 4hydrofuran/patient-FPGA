//==============================================================
//Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
//Tool Version Limit: 2026.06
//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//
//==============================================================
`timescale 1ns/1ps 

`ifndef W4A8_LINEAR_V1_SUBSYSTEM_PKG__SV          
    `define W4A8_LINEAR_V1_SUBSYSTEM_PKG__SV      
                                                     
    package w4a8_linear_v1_subsystem_pkg;               
                                                     
        import uvm_pkg::*;                           
        import file_agent_pkg::*;                    
        import axi_pkg::*;
                                                     
        `include "uvm_macros.svh"                  
                                                     
        `include "w4a8_linear_v1_config.sv"           
        `include "w4a8_linear_v1_reference_model.sv"  
        `include "w4a8_linear_v1_scoreboard.sv"       
        `include "w4a8_linear_v1_subsystem_monitor.sv"
        `include "w4a8_linear_v1_virtual_sequencer.sv"
        `include "w4a8_linear_v1_pkg_sequence_lib.sv" 
        `include "w4a8_linear_v1_env.sv"              
                                                     
    endpackage                                       
                                                     
`endif                                               
