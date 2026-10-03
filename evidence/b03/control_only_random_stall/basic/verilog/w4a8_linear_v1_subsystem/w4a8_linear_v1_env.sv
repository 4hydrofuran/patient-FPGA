//==============================================================
//Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
//Tool Version Limit: 2026.06
//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//
//==============================================================
`ifndef W4A8_LINEAR_V1_ENV__SV                                                                                   
    `define W4A8_LINEAR_V1_ENV__SV                                                                               
                                                                                                                    
    class axi_latency_gmem_w extends axi_latency;
        rand int    wr_latency;
        rand int    rd_latency;
        `uvm_object_utils_begin(axi_latency_gmem_w)
        `uvm_object_utils_end
        function new ( string name = "axi_latency_gmem_w" );
            super.new(name);
        endfunction
        virtual function int get_wr_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            wr_latency = delay;
            return wr_latency;
        endfunction
        virtual function int get_rd_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            rd_latency = delay;
            return rd_latency;
        endfunction
    endclass

    class axi_latency_gmem_sw extends axi_latency;
        rand int    wr_latency;
        rand int    rd_latency;
        `uvm_object_utils_begin(axi_latency_gmem_sw)
        `uvm_object_utils_end
        function new ( string name = "axi_latency_gmem_sw" );
            super.new(name);
        endfunction
        virtual function int get_wr_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            wr_latency = delay;
            return wr_latency;
        endfunction
        virtual function int get_rd_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            rd_latency = delay;
            return rd_latency;
        endfunction
    endclass

    class axi_latency_gmem_x extends axi_latency;
        rand int    wr_latency;
        rand int    rd_latency;
        `uvm_object_utils_begin(axi_latency_gmem_x)
        `uvm_object_utils_end
        function new ( string name = "axi_latency_gmem_x" );
            super.new(name);
        endfunction
        virtual function int get_wr_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            wr_latency = delay;
            return wr_latency;
        endfunction
        virtual function int get_rd_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            rd_latency = delay;
            return rd_latency;
        endfunction
    endclass

    class axi_latency_gmem_y extends axi_latency;
        rand int    wr_latency;
        rand int    rd_latency;
        `uvm_object_utils_begin(axi_latency_gmem_y)
        `uvm_object_utils_end
        function new ( string name = "axi_latency_gmem_y" );
            super.new(name);
        endfunction
        virtual function int get_wr_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            wr_latency = delay;
            return wr_latency;
        endfunction
        virtual function int get_rd_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            rd_latency = delay;
            return rd_latency;
        endfunction
    endclass

    class axi_latency_gmem_meta extends axi_latency;
        rand int    wr_latency;
        rand int    rd_latency;
        `uvm_object_utils_begin(axi_latency_gmem_meta)
        `uvm_object_utils_end
        function new ( string name = "axi_latency_gmem_meta" );
            super.new(name);
        endfunction
        virtual function int get_wr_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            wr_latency = delay;
            return wr_latency;
        endfunction
        virtual function int get_rd_lat();
            int delay;
            void'(std::randomize(delay) with { delay == 64;});
            rd_latency = delay;
            return rd_latency;
        endfunction
    endclass

    class axi_latency_control extends axi_latency;
        rand int    wctrl_latency;
        rand int    wdata_latency;
        rand int    wbrsp_latency;
        rand int    rctrl_latency;
        rand int    rdata_latency;
        `uvm_object_utils_begin(axi_latency_control)
        `uvm_object_utils_end
        function new ( string name = "axi_latency_control" );
            super.new(name);
        endfunction
        virtual function int get_wctrl_lat();
            int delay;
            void'(std::randomize(delay) with {
				delay dist {0:=8, 0:=1, 1:=1, [0:1]:/2};
				delay inside {[0:1]};
				});
            wctrl_latency = delay;
            return wctrl_latency;
        endfunction
        virtual function int get_wdata_lat();
            int delay;
            void'(std::randomize(delay) with {
				delay dist {0:=8, 0:=1, 1:=1, [0:1]:/2};
				delay inside {[0:1]};
				});
            wdata_latency = delay;
            return wdata_latency;
        endfunction
        virtual function int get_wbrsp_lat();
            int delay;
            void'(std::randomize(delay) with {
				delay dist {0:=8, 0:=1, 1:=1, [0:1]:/2};
				delay inside {[0:1]};
				});
            wbrsp_latency = delay;
            return wbrsp_latency;
        endfunction
        virtual function int get_rctrl_lat();
            int delay;
            void'(std::randomize(delay) with {
				delay dist {0:=8, 0:=1, 1:=1, [0:1]:/2};
				delay inside {[0:1]};
				});
            rctrl_latency = delay;
            return rctrl_latency;
        endfunction
        virtual function int get_rdata_lat();
            int delay;
            void'(std::randomize(delay) with {
				delay dist {0:=8, 0:=1, 1:=1, [0:1]:/2};
				delay inside {[0:1]};
				});
            rdata_latency = delay;
            return rdata_latency;
        endfunction
    endclass

                                                                                                                    
    class w4a8_linear_v1_env extends uvm_env;                                                                          
                                                                                                                    
        axi_latency_gmem_w    lat_gmem_w;
        axi_latency_gmem_sw    lat_gmem_sw;
        axi_latency_gmem_x    lat_gmem_x;
        axi_latency_gmem_y    lat_gmem_y;
        axi_latency_gmem_meta    lat_gmem_meta;
        axi_latency_control    lat_control;
        w4a8_linear_v1_virtual_sequencer w4a8_linear_v1_virtual_sqr;                                                      
        w4a8_linear_v1_config w4a8_linear_v1_cfg;                                                                         
                                                                                                                    
        axi_pkg::axi_env#(64,16,8,3,1) axi_master_gmem_w;
        axi_pkg::axi_env#(64,4,8,3,1) axi_master_gmem_sw;
        axi_pkg::axi_env#(64,16,8,3,1) axi_master_gmem_x;
        axi_pkg::axi_env#(64,4,8,3,1) axi_master_gmem_y;
        axi_pkg::axi_env#(64,64,8,3,1) axi_master_gmem_meta;
        axi_pkg::axi_env#(8,4,4,3,1) axi_lite_control;
                                                                                                                    
        w4a8_linear_v1_reference_model   refm;                                                                         
                                                                                                                    
        w4a8_linear_v1_subsystem_monitor subsys_mon;                                                                   
                                                                                                                    
        `uvm_component_utils_begin(w4a8_linear_v1_env)                                                                 
        `uvm_field_object (refm, UVM_DEFAULT | UVM_REFERENCE)                                                       
        `uvm_field_object (w4a8_linear_v1_virtual_sqr, UVM_DEFAULT | UVM_REFERENCE)                                    
        `uvm_field_object (w4a8_linear_v1_cfg        , UVM_DEFAULT)                                                    
        `uvm_component_utils_end                                                                                    
                                                                                                                    
        function new (string name = "w4a8_linear_v1_env", uvm_component parent = null);                              
            super.new(name, parent);                                                                                
        endfunction                                                                                                 
                                                                                                                    
        extern virtual function void build_phase(uvm_phase phase);                                                  
        extern virtual function void connect_phase(uvm_phase phase);                                                
        extern virtual task          run_phase(uvm_phase phase);                                                    
                                                                                                                    
    endclass                                                                                                        
                                                                                                                    
    function void w4a8_linear_v1_env::build_phase(uvm_phase phase);                                                    
        super.build_phase(phase);                                                                                   
        w4a8_linear_v1_cfg = w4a8_linear_v1_config::type_id::create("w4a8_linear_v1_cfg", this);                           
                                                                                                                    

        w4a8_linear_v1_cfg.gmem_w_cfg.set_default();
        w4a8_linear_v1_cfg.gmem_w_cfg.drv_type = axi_pkg::SLAVE;
        w4a8_linear_v1_cfg.gmem_w_cfg.reset_level = axi_pkg::RESET_LEVEL_LOW;
        lat_gmem_w = axi_latency_gmem_w::type_id::create("lat_gmem_w", this);
        w4a8_linear_v1_cfg.gmem_w_cfg.clatency = lat_gmem_w;
        w4a8_linear_v1_cfg.gmem_w_cfg.write_latency_mode = TRANSACTION_FIRST;
        w4a8_linear_v1_cfg.gmem_w_cfg.read_latency_mode = TRANSACTION_FIRST;
        uvm_config_db#(axi_pkg::axi_cfg)::set(this, "axi_master_gmem_w*", "cfg", w4a8_linear_v1_cfg.gmem_w_cfg);
        axi_master_gmem_w = axi_pkg::axi_env#(64,16,8,3,1)::type_id::create("axi_master_gmem_w", this);

        w4a8_linear_v1_cfg.gmem_sw_cfg.set_default();
        w4a8_linear_v1_cfg.gmem_sw_cfg.drv_type = axi_pkg::SLAVE;
        w4a8_linear_v1_cfg.gmem_sw_cfg.reset_level = axi_pkg::RESET_LEVEL_LOW;
        lat_gmem_sw = axi_latency_gmem_sw::type_id::create("lat_gmem_sw", this);
        w4a8_linear_v1_cfg.gmem_sw_cfg.clatency = lat_gmem_sw;
        w4a8_linear_v1_cfg.gmem_sw_cfg.write_latency_mode = TRANSACTION_FIRST;
        w4a8_linear_v1_cfg.gmem_sw_cfg.read_latency_mode = TRANSACTION_FIRST;
        uvm_config_db#(axi_pkg::axi_cfg)::set(this, "axi_master_gmem_sw*", "cfg", w4a8_linear_v1_cfg.gmem_sw_cfg);
        axi_master_gmem_sw = axi_pkg::axi_env#(64,4,8,3,1)::type_id::create("axi_master_gmem_sw", this);

        w4a8_linear_v1_cfg.gmem_x_cfg.set_default();
        w4a8_linear_v1_cfg.gmem_x_cfg.drv_type = axi_pkg::SLAVE;
        w4a8_linear_v1_cfg.gmem_x_cfg.reset_level = axi_pkg::RESET_LEVEL_LOW;
        lat_gmem_x = axi_latency_gmem_x::type_id::create("lat_gmem_x", this);
        w4a8_linear_v1_cfg.gmem_x_cfg.clatency = lat_gmem_x;
        w4a8_linear_v1_cfg.gmem_x_cfg.write_latency_mode = TRANSACTION_FIRST;
        w4a8_linear_v1_cfg.gmem_x_cfg.read_latency_mode = TRANSACTION_FIRST;
        uvm_config_db#(axi_pkg::axi_cfg)::set(this, "axi_master_gmem_x*", "cfg", w4a8_linear_v1_cfg.gmem_x_cfg);
        axi_master_gmem_x = axi_pkg::axi_env#(64,16,8,3,1)::type_id::create("axi_master_gmem_x", this);

        w4a8_linear_v1_cfg.gmem_y_cfg.set_default();
        w4a8_linear_v1_cfg.gmem_y_cfg.drv_type = axi_pkg::SLAVE;
        w4a8_linear_v1_cfg.gmem_y_cfg.reset_level = axi_pkg::RESET_LEVEL_LOW;
        lat_gmem_y = axi_latency_gmem_y::type_id::create("lat_gmem_y", this);
        w4a8_linear_v1_cfg.gmem_y_cfg.clatency = lat_gmem_y;
        w4a8_linear_v1_cfg.gmem_y_cfg.write_latency_mode = TRANSACTION_FIRST;
        w4a8_linear_v1_cfg.gmem_y_cfg.read_latency_mode = TRANSACTION_FIRST;
        uvm_config_db#(axi_pkg::axi_cfg)::set(this, "axi_master_gmem_y*", "cfg", w4a8_linear_v1_cfg.gmem_y_cfg);
        axi_master_gmem_y = axi_pkg::axi_env#(64,4,8,3,1)::type_id::create("axi_master_gmem_y", this);

        w4a8_linear_v1_cfg.gmem_meta_cfg.set_default();
        w4a8_linear_v1_cfg.gmem_meta_cfg.drv_type = axi_pkg::SLAVE;
        w4a8_linear_v1_cfg.gmem_meta_cfg.reset_level = axi_pkg::RESET_LEVEL_LOW;
        lat_gmem_meta = axi_latency_gmem_meta::type_id::create("lat_gmem_meta", this);
        w4a8_linear_v1_cfg.gmem_meta_cfg.clatency = lat_gmem_meta;
        w4a8_linear_v1_cfg.gmem_meta_cfg.write_latency_mode = TRANSACTION_FIRST;
        w4a8_linear_v1_cfg.gmem_meta_cfg.read_latency_mode = TRANSACTION_FIRST;
        uvm_config_db#(axi_pkg::axi_cfg)::set(this, "axi_master_gmem_meta*", "cfg", w4a8_linear_v1_cfg.gmem_meta_cfg);
        axi_master_gmem_meta = axi_pkg::axi_env#(64,64,8,3,1)::type_id::create("axi_master_gmem_meta", this);

        w4a8_linear_v1_cfg.control_cfg.set_default();
        w4a8_linear_v1_cfg.control_cfg.drv_type = axi_pkg::MASTER;
        w4a8_linear_v1_cfg.control_cfg.reset_level = axi_pkg::RESET_LEVEL_LOW;
        lat_control = axi_latency_control::type_id::create("lat_control", this);
        w4a8_linear_v1_cfg.control_cfg.clatency = lat_control;
        uvm_config_db#(axi_pkg::axi_cfg)::set(this, "axi_lite_control*", "cfg", w4a8_linear_v1_cfg.control_cfg);
        axi_lite_control = axi_pkg::axi_env#(8,4,4,3,1)::type_id::create("axi_lite_control", this);



        refm = w4a8_linear_v1_reference_model::type_id::create("refm", this);


        uvm_config_db#(w4a8_linear_v1_reference_model)::set(this, "*", "refm", refm);


        `uvm_info(this.get_full_name(), "set reference model by uvm_config_db", UVM_LOW)


        subsys_mon = w4a8_linear_v1_subsystem_monitor::type_id::create("subsys_mon", this);


        w4a8_linear_v1_virtual_sqr = w4a8_linear_v1_virtual_sequencer::type_id::create("w4a8_linear_v1_virtual_sqr", this);
        `uvm_info(this.get_full_name(), "build_phase done", UVM_LOW)
    endfunction


    function void w4a8_linear_v1_env::connect_phase(uvm_phase phase);
        super.connect_phase(phase);


        if(w4a8_linear_v1_cfg.gmem_w_cfg.drv_type==axi_pkg::MASTER ||w4a8_linear_v1_cfg.gmem_w_cfg.drv_type==axi_pkg::SLAVE)
            w4a8_linear_v1_virtual_sqr.gmem_w_sqr = axi_master_gmem_w.vsqr;
        axi_master_gmem_w.item_wtr_port.connect(subsys_mon.gmem_w_wtr_imp);
        axi_master_gmem_w.item_rtr_port.connect(subsys_mon.gmem_w_rtr_imp);
        uvm_callbacks#(axi_pkg::axi_state, axi_pkg::axi_state_cbs)::add(axi_master_gmem_w.state, refm.axi_memaccess_cb_gmem_w);
        if(w4a8_linear_v1_cfg.gmem_sw_cfg.drv_type==axi_pkg::MASTER ||w4a8_linear_v1_cfg.gmem_sw_cfg.drv_type==axi_pkg::SLAVE)
            w4a8_linear_v1_virtual_sqr.gmem_sw_sqr = axi_master_gmem_sw.vsqr;
        axi_master_gmem_sw.item_wtr_port.connect(subsys_mon.gmem_sw_wtr_imp);
        axi_master_gmem_sw.item_rtr_port.connect(subsys_mon.gmem_sw_rtr_imp);
        uvm_callbacks#(axi_pkg::axi_state, axi_pkg::axi_state_cbs)::add(axi_master_gmem_sw.state, refm.axi_memaccess_cb_gmem_sw);
        if(w4a8_linear_v1_cfg.gmem_x_cfg.drv_type==axi_pkg::MASTER ||w4a8_linear_v1_cfg.gmem_x_cfg.drv_type==axi_pkg::SLAVE)
            w4a8_linear_v1_virtual_sqr.gmem_x_sqr = axi_master_gmem_x.vsqr;
        axi_master_gmem_x.item_wtr_port.connect(subsys_mon.gmem_x_wtr_imp);
        axi_master_gmem_x.item_rtr_port.connect(subsys_mon.gmem_x_rtr_imp);
        uvm_callbacks#(axi_pkg::axi_state, axi_pkg::axi_state_cbs)::add(axi_master_gmem_x.state, refm.axi_memaccess_cb_gmem_x);
        if(w4a8_linear_v1_cfg.gmem_y_cfg.drv_type==axi_pkg::MASTER ||w4a8_linear_v1_cfg.gmem_y_cfg.drv_type==axi_pkg::SLAVE)
            w4a8_linear_v1_virtual_sqr.gmem_y_sqr = axi_master_gmem_y.vsqr;
        axi_master_gmem_y.item_wtr_port.connect(subsys_mon.gmem_y_wtr_imp);
        axi_master_gmem_y.item_rtr_port.connect(subsys_mon.gmem_y_rtr_imp);
        uvm_callbacks#(axi_pkg::axi_state, axi_pkg::axi_state_cbs)::add(axi_master_gmem_y.state, refm.axi_memaccess_cb_gmem_y);
        if(w4a8_linear_v1_cfg.gmem_meta_cfg.drv_type==axi_pkg::MASTER ||w4a8_linear_v1_cfg.gmem_meta_cfg.drv_type==axi_pkg::SLAVE)
            w4a8_linear_v1_virtual_sqr.gmem_meta_sqr = axi_master_gmem_meta.vsqr;
        axi_master_gmem_meta.item_wtr_port.connect(subsys_mon.gmem_meta_wtr_imp);
        axi_master_gmem_meta.item_rtr_port.connect(subsys_mon.gmem_meta_rtr_imp);
        uvm_callbacks#(axi_pkg::axi_state, axi_pkg::axi_state_cbs)::add(axi_master_gmem_meta.state, refm.axi_memaccess_cb_gmem_meta);
        if(w4a8_linear_v1_cfg.control_cfg.drv_type==axi_pkg::MASTER ||w4a8_linear_v1_cfg.control_cfg.drv_type==axi_pkg::SLAVE)
            w4a8_linear_v1_virtual_sqr.control_sqr = axi_lite_control.vsqr;
        axi_lite_control.item_wtr_port.connect(subsys_mon.control_wtr_imp);
        axi_lite_control.item_rtr_port.connect(subsys_mon.control_rtr_imp);
        refm.w4a8_linear_v1_cfg = w4a8_linear_v1_cfg;
        `uvm_info(this.get_full_name(), "connect phase done", UVM_LOW)
    endfunction


    task w4a8_linear_v1_env::run_phase(uvm_phase phase);
        `uvm_info(this.get_full_name(), "w4a8_linear_v1_env is running", UVM_LOW)
    endtask


`endif
