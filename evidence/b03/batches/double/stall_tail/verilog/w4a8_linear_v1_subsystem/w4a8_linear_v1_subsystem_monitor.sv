//==============================================================
//Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
//Tool Version Limit: 2026.06
//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//
//==============================================================

`ifndef W4A8_LINEAR_V1_SUBSYSTEM_MONITOR_SV
`define W4A8_LINEAR_V1_SUBSYSTEM_MONITOR_SV

`uvm_analysis_imp_decl(_axi_wtr_gmem_w)
`uvm_analysis_imp_decl(_axi_rtr_gmem_w)
`uvm_analysis_imp_decl(_axi_wtr_gmem_sw)
`uvm_analysis_imp_decl(_axi_rtr_gmem_sw)
`uvm_analysis_imp_decl(_axi_wtr_gmem_x)
`uvm_analysis_imp_decl(_axi_rtr_gmem_x)
`uvm_analysis_imp_decl(_axi_wtr_gmem_y)
`uvm_analysis_imp_decl(_axi_rtr_gmem_y)
`uvm_analysis_imp_decl(_axi_wtr_gmem_meta)
`uvm_analysis_imp_decl(_axi_rtr_gmem_meta)
`uvm_analysis_imp_decl(_axi_wtr_control)
`uvm_analysis_imp_decl(_axi_rtr_control)

class w4a8_linear_v1_subsystem_monitor extends uvm_component;

    w4a8_linear_v1_reference_model refm;
    w4a8_linear_v1_scoreboard scbd;

    `uvm_component_utils_begin(w4a8_linear_v1_subsystem_monitor)
    `uvm_component_utils_end

    uvm_analysis_imp_axi_wtr_gmem_w#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_w_wtr_imp;
    uvm_analysis_imp_axi_rtr_gmem_w#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_w_rtr_imp;
    uvm_analysis_imp_axi_wtr_gmem_sw#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_sw_wtr_imp;
    uvm_analysis_imp_axi_rtr_gmem_sw#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_sw_rtr_imp;
    uvm_analysis_imp_axi_wtr_gmem_x#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_x_wtr_imp;
    uvm_analysis_imp_axi_rtr_gmem_x#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_x_rtr_imp;
    uvm_analysis_imp_axi_wtr_gmem_y#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_y_wtr_imp;
    uvm_analysis_imp_axi_rtr_gmem_y#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_y_rtr_imp;
    uvm_analysis_imp_axi_wtr_gmem_meta#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_meta_wtr_imp;
    uvm_analysis_imp_axi_rtr_gmem_meta#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) gmem_meta_rtr_imp;
    uvm_analysis_imp_axi_wtr_control#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) control_wtr_imp;
    uvm_analysis_imp_axi_rtr_control#(axi_pkg::axi_transfer, w4a8_linear_v1_subsystem_monitor) control_rtr_imp;

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(w4a8_linear_v1_reference_model)::get(this, "", "refm", refm))
            `uvm_fatal(this.get_full_name(), "No refm from high level")
        `uvm_info(this.get_full_name(), "get reference model by uvm_config_db", UVM_MEDIUM)
        scbd = w4a8_linear_v1_scoreboard::type_id::create("scbd", this);
    endfunction

    virtual function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
    endfunction

    function new (string name = "", uvm_component parent = null);
        super.new(name, parent);
        gmem_w_wtr_imp = new("gmem_w_wtr_imp", this);
        gmem_w_rtr_imp = new("gmem_w_rtr_imp", this);
        gmem_sw_wtr_imp = new("gmem_sw_wtr_imp", this);
        gmem_sw_rtr_imp = new("gmem_sw_rtr_imp", this);
        gmem_x_wtr_imp = new("gmem_x_wtr_imp", this);
        gmem_x_rtr_imp = new("gmem_x_rtr_imp", this);
        gmem_y_wtr_imp = new("gmem_y_wtr_imp", this);
        gmem_y_rtr_imp = new("gmem_y_rtr_imp", this);
        gmem_meta_wtr_imp = new("gmem_meta_wtr_imp", this);
        gmem_meta_rtr_imp = new("gmem_meta_rtr_imp", this);
        control_wtr_imp = new("control_wtr_imp", this);
        control_rtr_imp = new("control_rtr_imp", this);
    endfunction

    virtual function void write_axi_wtr_gmem_w(axi_transfer tr);
        refm.write_axi_wtr_gmem_w(tr);
        scbd.write_axi_wtr_gmem_w(tr);
    endfunction

    virtual function void write_axi_rtr_gmem_w(axi_transfer tr);
        refm.write_axi_rtr_gmem_w(tr);
        scbd.write_axi_rtr_gmem_w(tr);
    endfunction

    virtual function void write_axi_wtr_gmem_sw(axi_transfer tr);
        refm.write_axi_wtr_gmem_sw(tr);
        scbd.write_axi_wtr_gmem_sw(tr);
    endfunction

    virtual function void write_axi_rtr_gmem_sw(axi_transfer tr);
        refm.write_axi_rtr_gmem_sw(tr);
        scbd.write_axi_rtr_gmem_sw(tr);
    endfunction

    virtual function void write_axi_wtr_gmem_x(axi_transfer tr);
        refm.write_axi_wtr_gmem_x(tr);
        scbd.write_axi_wtr_gmem_x(tr);
    endfunction

    virtual function void write_axi_rtr_gmem_x(axi_transfer tr);
        refm.write_axi_rtr_gmem_x(tr);
        scbd.write_axi_rtr_gmem_x(tr);
    endfunction

    virtual function void write_axi_wtr_gmem_y(axi_transfer tr);
        refm.write_axi_wtr_gmem_y(tr);
        scbd.write_axi_wtr_gmem_y(tr);
    endfunction

    virtual function void write_axi_rtr_gmem_y(axi_transfer tr);
        refm.write_axi_rtr_gmem_y(tr);
        scbd.write_axi_rtr_gmem_y(tr);
    endfunction

    virtual function void write_axi_wtr_gmem_meta(axi_transfer tr);
        refm.write_axi_wtr_gmem_meta(tr);
        scbd.write_axi_wtr_gmem_meta(tr);
    endfunction

    virtual function void write_axi_rtr_gmem_meta(axi_transfer tr);
        refm.write_axi_rtr_gmem_meta(tr);
        scbd.write_axi_rtr_gmem_meta(tr);
    endfunction

    virtual function void write_axi_wtr_control(axi_transfer tr);
        refm.write_axi_wtr_control(tr);
        scbd.write_axi_wtr_control(tr);
    endfunction

    virtual function void write_axi_rtr_control(axi_transfer tr);
        refm.write_axi_rtr_control(tr);
        scbd.write_axi_rtr_control(tr);
    endfunction
endclass
`endif
