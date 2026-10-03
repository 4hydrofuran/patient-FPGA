//==============================================================
//Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
//Tool Version Limit: 2026.06
//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//
//==============================================================
`ifndef W4A8_LINEAR_V1_CONFIG__SV                        
    `define W4A8_LINEAR_V1_CONFIG__SV                    
                                                            
    class w4a8_linear_v1_config extends uvm_object;            
                                                            
        int check_ena;                                      
        int cover_ena;                                      
        axi_pkg::axi_cfg gmem_w_cfg;
        axi_pkg::axi_cfg gmem_sw_cfg;
        axi_pkg::axi_cfg gmem_x_cfg;
        axi_pkg::axi_cfg gmem_y_cfg;
        axi_pkg::axi_cfg gmem_meta_cfg;
        axi_pkg::axi_cfg control_cfg;

        `uvm_object_utils_begin(w4a8_linear_v1_config)         
        `uvm_field_object(gmem_w_cfg, UVM_DEFAULT);
        `uvm_field_object(gmem_sw_cfg, UVM_DEFAULT);
        `uvm_field_object(gmem_x_cfg, UVM_DEFAULT);
        `uvm_field_object(gmem_y_cfg, UVM_DEFAULT);
        `uvm_field_object(gmem_meta_cfg, UVM_DEFAULT);
        `uvm_field_object(control_cfg, UVM_DEFAULT);
        `uvm_field_int   (check_ena , UVM_DEFAULT)          
        `uvm_field_int   (cover_ena , UVM_DEFAULT)          
        `uvm_object_utils_end                               

        function new (string name = "w4a8_linear_v1_config");
            super.new(name);                                
            gmem_w_cfg = new("gmem_w_cfg", 1);
            gmem_sw_cfg = new("gmem_sw_cfg", 1);
            gmem_x_cfg = new("gmem_x_cfg", 1);
            gmem_y_cfg = new("gmem_y_cfg", 1);
            gmem_meta_cfg = new("gmem_meta_cfg", 1);
            control_cfg = axi_pkg::axi_cfg::type_id::create("control_cfg");
        endfunction                                         
                                                            
    endclass                                                
                                                            
`endif                                                      
