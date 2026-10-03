//==============================================================
//Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
//Tool Version Limit: 2026.06
//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//
//==============================================================
`ifndef W4A8_LINEAR_V1_VIRTUAL_SEQUENCER__SV                        
    `define W4A8_LINEAR_V1_VIRTUAL_SEQUENCER__SV                    
                                                                       
    class w4a8_linear_v1_virtual_sequencer extends uvm_sequencer;         
        axi_pkg::axi_virtual_sequencer gmem_w_sqr; 
        axi_pkg::axi_virtual_sequencer gmem_sw_sqr; 
        axi_pkg::axi_virtual_sequencer gmem_x_sqr; 
        axi_pkg::axi_virtual_sequencer gmem_y_sqr; 
        axi_pkg::axi_virtual_sequencer gmem_meta_sqr; 
        axi_pkg::axi_virtual_sequencer control_sqr; 
 
        function new (string name, uvm_component parent);              
            super.new(name, parent);                                   
            //`uvm_info(this.get_full_name(), "new is called", UVM_LOW)
        endfunction                                                    
                                                                       
        `uvm_component_utils_begin(w4a8_linear_v1_virtual_sequencer)      
        `uvm_component_utils_end                                       
                                                                       
    endclass

`endif
