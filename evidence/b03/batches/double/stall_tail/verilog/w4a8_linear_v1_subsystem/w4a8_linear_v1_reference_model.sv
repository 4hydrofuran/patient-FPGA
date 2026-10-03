//==============================================================
//Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
//Tool Version Limit: 2026.06
//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//
//==============================================================

`ifndef W4A8_LINEAR_V1_REFERENCE_MODEL_SV
`define W4A8_LINEAR_V1_REFERENCE_MODEL_SV
typedef class w4a8_linear_v1_reference_model;
class memaccess_axi_state_cbs extends axi_pkg::axi_state_cbs;
    w4a8_linear_v1_reference_model refm;
    string memid;
    //function new(string name="memaccess_axi_state_cbs");
    //    super.new(name);
    //endfunction
    virtual function void memmodel_read_fromar(ref logic[7:0] data[$], input longint addr, input longint len);
        if(memid=="gmem_w") refm.mem_blk_pages_gmem_w.read_elems_pipepage(data, addr, len);
        if(memid=="gmem_sw") refm.mem_blk_pages_gmem_sw.read_elems_pipepage(data, addr, len);
        if(memid=="gmem_x") refm.mem_blk_pages_gmem_x.read_elems_pipepage(data, addr, len);
        if(memid=="gmem_y") refm.mem_blk_pages_gmem_y.read_elems_pipepage(data, addr, len);
        if(memid=="gmem_meta") refm.mem_blk_pages_gmem_meta.read_elems_pipepage(data, addr, len);
    endfunction
endclass

class w4a8_linear_v1_reference_model extends uvm_component;
`define TV_IN_gmem_w "../tv/cdatafile/c.w4a8_linear_v1.autotvin_gmem_w.dat"
`define TV_OUT_gmem_w "../tv/rtldatafile/rtl.w4a8_linear_v1.autotvout_gmem_w.dat"
`define TV_IN_OFFSET_w_packed "../tv/cdatafile/c.w4a8_linear_v1.autotvin_w_packed.dat"
`define TV_IN_gmem_sw "../tv/cdatafile/c.w4a8_linear_v1.autotvin_gmem_sw.dat"
`define TV_OUT_gmem_sw "../tv/rtldatafile/rtl.w4a8_linear_v1.autotvout_gmem_sw.dat"
`define TV_IN_OFFSET_sw "../tv/cdatafile/c.w4a8_linear_v1.autotvin_sw.dat"
`define TV_IN_gmem_x "../tv/cdatafile/c.w4a8_linear_v1.autotvin_gmem_x.dat"
`define TV_OUT_gmem_x "../tv/rtldatafile/rtl.w4a8_linear_v1.autotvout_gmem_x.dat"
`define TV_IN_OFFSET_xq "../tv/cdatafile/c.w4a8_linear_v1.autotvin_xq.dat"
`define TV_IN_OFFSET_sx "../tv/cdatafile/c.w4a8_linear_v1.autotvin_sx.dat"
`define TV_IN_gmem_y "../tv/cdatafile/c.w4a8_linear_v1.autotvin_gmem_y.dat"
`define TV_OUT_gmem_y "../tv/rtldatafile/rtl.w4a8_linear_v1.autotvout_gmem_y.dat"
`define TV_IN_OFFSET_y "../tv/cdatafile/c.w4a8_linear_v1.autotvin_y.dat"
`define TV_IN_gmem_meta "../tv/cdatafile/c.w4a8_linear_v1.autotvin_gmem_meta.dat"
`define TV_OUT_gmem_meta "../tv/rtldatafile/rtl.w4a8_linear_v1.autotvout_gmem_meta.dat"
`define TV_IN_OFFSET_meta "../tv/cdatafile/c.w4a8_linear_v1.autotvin_meta.dat"
`define TV_IN_w_packed "../tv/cdatafile/c.w4a8_linear_v1.autotvin_w_packed.dat"
`define TV_OUT_w_packed ""
`define TV_IN_sw "../tv/cdatafile/c.w4a8_linear_v1.autotvin_sw.dat"
`define TV_OUT_sw ""
`define TV_IN_xq "../tv/cdatafile/c.w4a8_linear_v1.autotvin_xq.dat"
`define TV_OUT_xq ""
`define TV_IN_sx "../tv/cdatafile/c.w4a8_linear_v1.autotvin_sx.dat"
`define TV_OUT_sx ""
`define TV_IN_y "../tv/cdatafile/c.w4a8_linear_v1.autotvin_y.dat"
`define TV_OUT_y ""
`define TV_IN_meta "../tv/cdatafile/c.w4a8_linear_v1.autotvin_meta.dat"
`define TV_OUT_meta ""
`define TV_IN_t "../tv/cdatafile/c.w4a8_linear_v1.autotvin_t.dat"
`define TV_OUT_t ""
`define TV_IN_n "../tv/cdatafile/c.w4a8_linear_v1.autotvin_n.dat"
`define TV_OUT_n ""
`define TV_IN_k "../tv/cdatafile/c.w4a8_linear_v1.autotvin_k.dat"
`define TV_OUT_k ""
`define TV_IN_w_bytes "../tv/cdatafile/c.w4a8_linear_v1.autotvin_w_bytes.dat"
`define TV_OUT_w_bytes ""
`define TV_IN_sw_bytes "../tv/cdatafile/c.w4a8_linear_v1.autotvin_sw_bytes.dat"
`define TV_OUT_sw_bytes ""
`define TV_IN_x_bytes "../tv/cdatafile/c.w4a8_linear_v1.autotvin_x_bytes.dat"
`define TV_OUT_x_bytes ""
`define TV_IN_sx_bytes "../tv/cdatafile/c.w4a8_linear_v1.autotvin_sx_bytes.dat"
`define TV_OUT_sx_bytes ""
`define TV_IN_y_bytes "../tv/cdatafile/c.w4a8_linear_v1.autotvin_y_bytes.dat"
`define TV_OUT_y_bytes ""
`define TV_IN_meta_bytes "../tv/cdatafile/c.w4a8_linear_v1.autotvin_meta_bytes.dat"
`define TV_OUT_meta_bytes ""
`define TV_IN_job_id "../tv/cdatafile/c.w4a8_linear_v1.autotvin_job_id.dat"
`define TV_OUT_job_id ""
`define TV_IN_abi_version "../tv/cdatafile/c.w4a8_linear_v1.autotvin_abi_version.dat"
`define TV_OUT_abi_version ""
    bit  write_data_finish_control;
    event allaxilite_write_data_finish;
    event write_start_finish;
    int trans_num_total = 7;
    int trans_num_idx;
    int ap_done_cnt=1;
    event dut2tb_ap_ready;
    event dut2tb_ap_done;
    event ap_ready_for_nexttrans;
    event ap_done_for_nexttrans;
    event finish;
    w4a8_linear_v1_config w4a8_linear_v1_cfg;
    virtual interface misc_interface misc_if;

    mem_model_pages_with_diffofst#(128,8) mem_blk_pages_gmem_w;
    int blk_id_gmem_w = 0;
    memaccess_axi_state_cbs axi_memaccess_cb_gmem_w;

    mem_model_pages_with_diffofst#(32,8) mem_blk_pages_gmem_sw;
    int blk_id_gmem_sw = 0;
    memaccess_axi_state_cbs axi_memaccess_cb_gmem_sw;

    mem_model_pages_with_diffofst#(128,8) mem_blk_pages_gmem_x;
    int blk_id_gmem_x = 0;
    memaccess_axi_state_cbs axi_memaccess_cb_gmem_x;

    mem_model_pages_with_diffofst#(32,8) mem_blk_pages_gmem_y;
    int blk_id_gmem_y = 0;
    memaccess_axi_state_cbs axi_memaccess_cb_gmem_y;

    mem_model_pages_with_diffofst#(512,8) mem_blk_pages_gmem_meta;
    int blk_id_gmem_meta = 0;
    memaccess_axi_state_cbs axi_memaccess_cb_gmem_meta;

    mem_model_pages#(32,8) mem_blk_pages_control_t;
    mem_model_pages#(32,8) mem_blk_pages_control_n;
    mem_model_pages#(32,8) mem_blk_pages_control_k;
    mem_model_pages#(64,8) mem_blk_pages_control_w_bytes;
    mem_model_pages#(64,8) mem_blk_pages_control_sw_bytes;
    mem_model_pages#(64,8) mem_blk_pages_control_x_bytes;
    mem_model_pages#(64,8) mem_blk_pages_control_sx_bytes;
    mem_model_pages#(64,8) mem_blk_pages_control_y_bytes;
    mem_model_pages#(64,8) mem_blk_pages_control_meta_bytes;
    mem_model_pages#(64,8) mem_blk_pages_control_job_id;
    mem_model_pages#(32,8) mem_blk_pages_control_abi_version;
    
    `uvm_component_utils_begin(w4a8_linear_v1_reference_model)
        `uvm_field_int (trans_num_idx, UVM_DEFAULT)
    `uvm_component_utils_end

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if(!uvm_config_db#(virtual misc_interface)::get(this, "", "misc_if", misc_if))
            `uvm_fatal(this.get_full_name(), "No misc_if from high level")
        axi_memaccess_cb_gmem_w = new;
        axi_memaccess_cb_gmem_w.refm = this;
        axi_memaccess_cb_gmem_w.memid = "gmem_w";
        axi_memaccess_cb_gmem_sw = new;
        axi_memaccess_cb_gmem_sw.refm = this;
        axi_memaccess_cb_gmem_sw.memid = "gmem_sw";
        axi_memaccess_cb_gmem_x = new;
        axi_memaccess_cb_gmem_x.refm = this;
        axi_memaccess_cb_gmem_x.memid = "gmem_x";
        axi_memaccess_cb_gmem_y = new;
        axi_memaccess_cb_gmem_y.refm = this;
        axi_memaccess_cb_gmem_y.memid = "gmem_y";
        axi_memaccess_cb_gmem_meta = new;
        axi_memaccess_cb_gmem_meta.refm = this;
        axi_memaccess_cb_gmem_meta.memid = "gmem_meta";
    endfunction

    function new (string name = "", uvm_component parent = null);
        super.new (name, parent);
        trans_num_idx= 0;
    endfunction

    virtual task run_phase(uvm_phase phase);
        string fpath[$];
misc_if.dut2tb_ap_done = 0;

        fpath.push_back(`TV_IN_t);
        mem_blk_pages_control_t = mem_model_pages#(32,8)::type_id::create("mem_blk_pages_control_t");
        mem_blk_pages_control_t.tvinload_pagechk_atinit(fpath, 1*((32+7)/8), 0, 88);
        fpath.delete;


        fpath.push_back(`TV_IN_n);
        mem_blk_pages_control_n = mem_model_pages#(32,8)::type_id::create("mem_blk_pages_control_n");
        mem_blk_pages_control_n.tvinload_pagechk_atinit(fpath, 1*((32+7)/8), 0, 96);
        fpath.delete;


        fpath.push_back(`TV_IN_k);
        mem_blk_pages_control_k = mem_model_pages#(32,8)::type_id::create("mem_blk_pages_control_k");
        mem_blk_pages_control_k.tvinload_pagechk_atinit(fpath, 1*((32+7)/8), 0, 104);
        fpath.delete;


        fpath.push_back(`TV_IN_w_bytes);
        mem_blk_pages_control_w_bytes = mem_model_pages#(64,8)::type_id::create("mem_blk_pages_control_w_bytes");
        mem_blk_pages_control_w_bytes.tvinload_pagechk_atinit(fpath, 1*((64+7)/8), 0, 112);
        fpath.delete;


        fpath.push_back(`TV_IN_sw_bytes);
        mem_blk_pages_control_sw_bytes = mem_model_pages#(64,8)::type_id::create("mem_blk_pages_control_sw_bytes");
        mem_blk_pages_control_sw_bytes.tvinload_pagechk_atinit(fpath, 1*((64+7)/8), 0, 124);
        fpath.delete;


        fpath.push_back(`TV_IN_x_bytes);
        mem_blk_pages_control_x_bytes = mem_model_pages#(64,8)::type_id::create("mem_blk_pages_control_x_bytes");
        mem_blk_pages_control_x_bytes.tvinload_pagechk_atinit(fpath, 1*((64+7)/8), 0, 136);
        fpath.delete;


        fpath.push_back(`TV_IN_sx_bytes);
        mem_blk_pages_control_sx_bytes = mem_model_pages#(64,8)::type_id::create("mem_blk_pages_control_sx_bytes");
        mem_blk_pages_control_sx_bytes.tvinload_pagechk_atinit(fpath, 1*((64+7)/8), 0, 148);
        fpath.delete;


        fpath.push_back(`TV_IN_y_bytes);
        mem_blk_pages_control_y_bytes = mem_model_pages#(64,8)::type_id::create("mem_blk_pages_control_y_bytes");
        mem_blk_pages_control_y_bytes.tvinload_pagechk_atinit(fpath, 1*((64+7)/8), 0, 160);
        fpath.delete;


        fpath.push_back(`TV_IN_meta_bytes);
        mem_blk_pages_control_meta_bytes = mem_model_pages#(64,8)::type_id::create("mem_blk_pages_control_meta_bytes");
        mem_blk_pages_control_meta_bytes.tvinload_pagechk_atinit(fpath, 1*((64+7)/8), 0, 172);
        fpath.delete;


        fpath.push_back(`TV_IN_job_id);
        mem_blk_pages_control_job_id = mem_model_pages#(64,8)::type_id::create("mem_blk_pages_control_job_id");
        mem_blk_pages_control_job_id.tvinload_pagechk_atinit(fpath, 1*((64+7)/8), 0, 184);
        fpath.delete;


        fpath.push_back(`TV_IN_abi_version);
        mem_blk_pages_control_abi_version = mem_model_pages#(32,8)::type_id::create("mem_blk_pages_control_abi_version");
        mem_blk_pages_control_abi_version.tvinload_pagechk_atinit(fpath, 1*((32+7)/8), 0, 196);
        fpath.delete;

        fpath.push_back(`TV_IN_gmem_w);
        mem_blk_pages_gmem_w = mem_model_pages_with_diffofst#(128,8)::type_id::create("mem_blk_pages_gmem_w");
        mem_blk_pages_gmem_w.whole_page_size=2179328;
        mem_blk_pages_gmem_w.maxi_bundlevar_fpath["w_packed"]=`TV_IN_OFFSET_w_packed;
        mem_blk_pages_gmem_w.set_binary(1);
        mem_blk_pages_gmem_w.tvinload_pagechk_atinit(fpath, 136192*((128+7)/8), 0, 0);
        fpath.delete();

        fpath.push_back(`TV_IN_gmem_sw);
        mem_blk_pages_gmem_sw = mem_model_pages_with_diffofst#(32,8)::type_id::create("mem_blk_pages_gmem_sw");
        mem_blk_pages_gmem_sw.whole_page_size=136256;
        mem_blk_pages_gmem_sw.maxi_bundlevar_fpath["sw"]=`TV_IN_OFFSET_sw;
        mem_blk_pages_gmem_sw.set_binary(1);
        mem_blk_pages_gmem_sw.tvinload_pagechk_atinit(fpath, 34048*((32+7)/8), 0, 0);
        fpath.delete();

        fpath.push_back(`TV_IN_gmem_x);
        mem_blk_pages_gmem_x = mem_model_pages_with_diffofst#(128,8)::type_id::create("mem_blk_pages_gmem_x");
        mem_blk_pages_gmem_x.whole_page_size=39200;
        mem_blk_pages_gmem_x.maxi_bundlevar_fpath["xq"]=`TV_IN_OFFSET_xq;
        mem_blk_pages_gmem_x.maxi_bundlevar_fpath["sx"]=`TV_IN_OFFSET_sx;
        mem_blk_pages_gmem_x.set_binary(1);
        mem_blk_pages_gmem_x.tvinload_pagechk_atinit(fpath, 2434*((128+7)/8), 0, 0);
        fpath.delete();

        fpath.push_back(`TV_IN_gmem_y);
        mem_blk_pages_gmem_y = mem_model_pages_with_diffofst#(32,8)::type_id::create("mem_blk_pages_gmem_y");
        mem_blk_pages_gmem_y.whole_page_size=155712;
        mem_blk_pages_gmem_y.maxi_bundlevar_fpath["y"]=`TV_IN_OFFSET_y;
        mem_blk_pages_gmem_y.set_binary(1);
        mem_blk_pages_gmem_y.tvinload_pagechk_atinit(fpath, 38912*((32+7)/8), 0, 0);
        mem_blk_pages_gmem_y.tvoutdump_atinit(`TV_OUT_gmem_y);
        fpath.delete();

        fpath.push_back(`TV_IN_gmem_meta);
        mem_blk_pages_gmem_meta = mem_model_pages_with_diffofst#(512,8)::type_id::create("mem_blk_pages_gmem_meta");
        mem_blk_pages_gmem_meta.whole_page_size=1088;
        mem_blk_pages_gmem_meta.maxi_bundlevar_fpath["meta"]=`TV_IN_OFFSET_meta;
        mem_blk_pages_gmem_meta.tvinload_pagechk_atinit(fpath, 1*((512+7)/8), 0, 0);
        mem_blk_pages_gmem_meta.tvoutdump_atinit(`TV_OUT_gmem_meta);
        fpath.delete();

        fork
            forever begin
                fork
                    begin
                        wait(write_data_finish_control);
                    end
                join
                `uvm_info("", "trigger_allaxilite_write_data_finish", UVM_LOW)
                @(posedge misc_if.clock);
                write_data_finish_control = 0;
                -> allaxilite_write_data_finish;
            end
            forever begin
                //this is non-pipeline case
                forever begin
                    @(negedge misc_if.clock);
                    if(misc_if.dut2tb_ap_done===1) break;
                end
                @(posedge misc_if.clock);
                @allaxilite_write_data_finish;
                @(posedge misc_if.clock);
                -> ap_ready_for_nexttrans;
                `uvm_info(this.get_full_name(), "trigger event ap_ready_for_nexttrans", UVM_LOW)
                fork
                    begin
                        misc_if.ap_ready_for_nexttrans = 1;
                        @(posedge misc_if.clock);
                        misc_if.ap_ready_for_nexttrans = 0;
                    end
                join_none
            end
            forever begin
                forever begin
                    @(negedge misc_if.clock);
                    if(misc_if.dut2tb_ap_done===1) break;
                end
                @(posedge misc_if.clock);
                fork
                    begin
                        @(negedge misc_if.clock);
                        -> misc_if.dut2tb_ap_done_evt;
                        #0;
                        -> misc_if.dut2tb_ap_ready_evt;
                    end
                join_none
                -> ap_done_for_nexttrans;
                `uvm_info(this.get_full_name(), "trigger event ap_done_for_nexttrans", UVM_LOW)
                fork
                    begin
                        misc_if.ap_done_for_nexttrans = 1;
                        @(posedge misc_if.clock);
                        misc_if.ap_done_for_nexttrans = 0;
                    end
                join_none
            end

            for(int i=1; i<7; i++) begin
                @dut2tb_ap_ready;
                mem_blk_pages_gmem_w.incr_rd_page_idx() ;
                mem_blk_pages_gmem_sw.incr_rd_page_idx() ;
                mem_blk_pages_gmem_x.incr_rd_page_idx() ;
                mem_blk_pages_gmem_y.incr_rd_page_idx() ;
                mem_blk_pages_gmem_meta.incr_rd_page_idx() ;
            end
            forever begin
                forever begin
                    @(negedge misc_if.clock);
                    if (misc_if.dut2tb_ap_ready === 1)   break;
                end
                @(posedge misc_if.clock);
                `uvm_info(this.get_full_name(), "trigger event DUT2TB_AP_READY", UVM_LOW)
                -> dut2tb_ap_ready;
                 misc_if.tb2dut_ap_start = 0;
            end
            forever begin
                forever begin
                    @(negedge misc_if.clock);
                    if (misc_if.dut2tb_ap_done_kernel === 1)   break;
                end
                @(posedge misc_if.clock);
                fork
                    begin
                        @(negedge misc_if.clock);
                        `uvm_info(this.get_full_name(), "trigger event dut2tb_ap_done_kernel_evt", UVM_LOW)
                        -> misc_if.dut2tb_ap_done_kernel_evt;
                    end
                join_none
            end
        join
    endtask

    virtual function void write_axi_wtr_gmem_w(axi_pkg::axi_transfer tr);
        mem_blk_pages_gmem_w.write_elems_pipepage(tr.data,tr.byte_addr);
    endfunction

    virtual function void write_axi_rtr_gmem_w(axi_pkg::axi_transfer tr);
    endfunction

    virtual function void write_axi_wtr_gmem_sw(axi_pkg::axi_transfer tr);
        mem_blk_pages_gmem_sw.write_elems_pipepage(tr.data,tr.byte_addr);
    endfunction

    virtual function void write_axi_rtr_gmem_sw(axi_pkg::axi_transfer tr);
    endfunction

    virtual function void write_axi_wtr_gmem_x(axi_pkg::axi_transfer tr);
        mem_blk_pages_gmem_x.write_elems_pipepage(tr.data,tr.byte_addr);
    endfunction

    virtual function void write_axi_rtr_gmem_x(axi_pkg::axi_transfer tr);
    endfunction

    virtual function void write_axi_wtr_gmem_y(axi_pkg::axi_transfer tr);
        mem_blk_pages_gmem_y.write_elems_pipepage(tr.data,tr.byte_addr);
    endfunction

    virtual function void write_axi_rtr_gmem_y(axi_pkg::axi_transfer tr);
    endfunction

    virtual function void write_axi_wtr_gmem_meta(axi_pkg::axi_transfer tr);
        mem_blk_pages_gmem_meta.write_elems_pipepage(tr.data,tr.byte_addr);
    endfunction

    virtual function void write_axi_rtr_gmem_meta(axi_pkg::axi_transfer tr);
    endfunction

    virtual function void write_axi_wtr_control(axi_pkg::axi_transfer tr);
        if(tr.addr == 0 && tr.len == 0 && tr.data[0][0]==1) begin //addr 0 and bit 0 are parameter
            -> write_start_finish;
            misc_if.tb2dut_ap_start = 1;
        end
    endfunction
    virtual function void write_axi_rtr_control(axi_pkg::axi_transfer tr);
            `uvm_info("receive axi read data", tr.sprint(), UVM_HIGH)
        if(tr.addr == 0 && tr.len == 0) begin
            if(tr.data[0][1]==1) begin  //bit 1 is parameter
                `uvm_info("status polling", "ap_done is polled", UVM_LOW);
                fork
                    begin
                        misc_if.dut2tb_ap_done = 1;
                        @(posedge misc_if.clock);
                        #0;
                        misc_if.dut2tb_ap_done = 0;
                        misc_if.tb2dut_ap_continue = 0;
                        -> dut2tb_ap_done;
                    end
                join_none
            end
            begin
                misc_if.dut2tb_ap_idle = tr.data[0][2];
            end
        end else begin
        end
    endfunction
endclass
`endif
