//==============================================================
//Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
//Tool Version Limit: 2026.06
//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//
//==============================================================
`ifndef W4A8_LINEAR_V1_SCOREBOARD__SV                                                       
    `define W4A8_LINEAR_V1_SCOREBOARD__SV                                                   
                                                                                               
                                                                                               
    class w4a8_linear_v1_scoreboard extends uvm_component;                                        
                                                                                               
        w4a8_linear_v1_reference_model refm;                                                      
                                                                                               
                                                                                               
        `uvm_component_utils_begin(w4a8_linear_v1_scoreboard)                                     
        `uvm_field_object(refm  , UVM_DEFAULT)                                                 
        `uvm_component_utils_end                                                               
                                                                                               
        virtual function void build_phase(uvm_phase phase);                                    
            if (!uvm_config_db #(w4a8_linear_v1_reference_model)::get(this, "", "refm", refm))
                `uvm_fatal(this.get_full_name(), "No refm from high level")                  
            `uvm_info(this.get_full_name(), "get reference model by uvm_config_db", UVM_MEDIUM) 
                                                                                               
        endfunction                                                                            
                                                                                               
        function new (string name = "", uvm_component parent = null);                        
            super.new(name, parent);                                                           
        endfunction                                                                            
                                                                                               
        virtual task run_phase(uvm_phase phase);                                               

            fork                                                                               
                forever begin
                    @refm.allaxilite_write_data_finish;
                    `uvm_info(this.get_full_name(), "receive allaxilite_write_finish axilite write_mem_page_process", UVM_LOW)
                    void'(refm.mem_blk_pages_control_t.pages.pop_front());
                    void'(refm.mem_blk_pages_control_n.pages.pop_front());
                    void'(refm.mem_blk_pages_control_k.pages.pop_front());
                    void'(refm.mem_blk_pages_control_w_bytes.pages.pop_front());
                    void'(refm.mem_blk_pages_control_sw_bytes.pages.pop_front());
                    void'(refm.mem_blk_pages_control_x_bytes.pages.pop_front());
                    void'(refm.mem_blk_pages_control_sx_bytes.pages.pop_front());
                    void'(refm.mem_blk_pages_control_y_bytes.pages.pop_front());
                    void'(refm.mem_blk_pages_control_meta_bytes.pages.pop_front());
                    void'(refm.mem_blk_pages_control_job_id.pages.pop_front());
                    void'(refm.mem_blk_pages_control_abi_version.pages.pop_front());
                end
                                                                                               
                forever begin
                    @refm.dut2tb_ap_done;
                    `uvm_info(this.get_full_name(), "receive dut2tb_ap_done and do axim dump", UVM_LOW)
                            refm.mem_blk_pages_gmem_w.tvout_dump_frontpage(0);
                            refm.mem_blk_pages_gmem_sw.tvout_dump_frontpage(0);
                            refm.mem_blk_pages_gmem_x.tvout_dump_frontpage(0);
                            refm.mem_blk_pages_gmem_y.tvout_dump_frontpage(1);
                            refm.mem_blk_pages_gmem_meta.tvout_dump_frontpage(1);
                end                                                                            
                begin                                                                          
                    @refm.finish;                                                              
                    `uvm_info(this.get_full_name(), "receive FINISH", UVM_LOW)               
                end                                                                            
            join                                                                               
        endtask                                                                                
                                                                                               
        virtual function void write_axi_wtr_gmem_w(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_rtr_gmem_w(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_wtr_gmem_sw(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_rtr_gmem_sw(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_wtr_gmem_x(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_rtr_gmem_x(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_wtr_gmem_y(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_rtr_gmem_y(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_wtr_gmem_meta(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_rtr_gmem_meta(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_wtr_control(axi_pkg::axi_transfer tr);
        endfunction

        virtual function void write_axi_rtr_control(axi_pkg::axi_transfer tr);
        endfunction

    endclass                                                                                   
                                                                                               
`endif                                                                                         
