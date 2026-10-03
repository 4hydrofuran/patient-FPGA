//==============================================================
//Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
//Tool Version Limit: 2026.06
//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//
//==============================================================
`ifndef W4A8_LINEAR_V1_SUBSYS_TEST_SEQUENCE_LIB__SV                                              
    `define W4A8_LINEAR_V1_SUBSYS_TEST_SEQUENCE_LIB__SV                                          
                                                                                                    
                                                                                                    
    `include "uvm_macros.svh"                                                                     
                                                                                                    
    // Delay kinds used in this test sequence                                                       
    typedef enum int {                                                                              
        TB_DELAY_NONE,                                                                              
        DELAY_DIRECTIO_BEFORE_FORCE,  // delay before force used in directio on s_axilite           
        DELAY_MAXI                    // delay for m_axi to make sure mem incr_rd_page_idx is called first
    } tb_delay_e;                                                                                   
                                                                                                    
    // Delay application task                                                                       
    task automatic tb_apply_delay(tb_delay_e kind);                                                 
        case (kind)                                                                                 
            TB_DELAY_NONE:                     ;         // no delay                                
            DELAY_DIRECTIO_BEFORE_FORCE: #0.001;                                                    
            DELAY_MAXI:                  #0.001;                                                    
            default:                           ;                                                    
        endcase                                                                                     
    endtask                                                                                         
                                                                                                    
    class w4a8_linear_v1_subsys_test_sequence_lib extends uvm_sequence;                                
                                                                                                    
        function new (string name = "w4a8_linear_v1_subsys_test_sequence_lib");                      
            super.new(name);                                                                        
            `uvm_info(this.get_full_name(), "new is called", UVM_LOW)                             
        endfunction                                                                                 
                                                                                                    
        `uvm_object_utils(w4a8_linear_v1_subsys_test_sequence_lib)                                     
        `uvm_declare_p_sequencer(w4a8_linear_v1_virtual_sequencer)                                     
                                                                                                    
        virtual task body();                                                                        
            uvm_phase starting_phase;                                                               
            virtual interface misc_interface misc_if;                                               
            w4a8_linear_v1_reference_model refm;                                                       
                                                                                                    
            axi_pkg::axi_slave_sequence#(64,16,8,3,1) axi_slave_gmem_w_seq;
            axi_pkg::axi_slave_sequence#(64,4,8,3,1) axi_slave_gmem_sw_seq;
            axi_pkg::axi_slave_sequence#(64,16,8,3,1) axi_slave_gmem_x_seq;
            axi_pkg::axi_slave_sequence#(64,4,8,3,1) axi_slave_gmem_y_seq;
            axi_pkg::axi_slave_sequence#(64,64,8,3,1) axi_slave_gmem_meta_seq;
            axi_pkg::axi_busdatas_master_sequence#(8, 32) axi_master_wr_control_seq;
            axi_pkg::axi_busdatas_master_sequence#(8, 32) axi_master_poll_control_seq;

            if (!uvm_config_db#(w4a8_linear_v1_reference_model)::get(p_sequencer,"", "refm", refm))
                `uvm_fatal(this.get_full_name(), "No reference model")
            `uvm_info(this.get_full_name(), "get reference model by uvm_config_db", UVM_LOW)

            `uvm_info(this.get_full_name(), "body is called", UVM_LOW)
            starting_phase = this.get_starting_phase();
            if (starting_phase != null) begin
                `uvm_info(this.get_full_name(), "starting_phase not null", UVM_LOW)
                starting_phase.raise_objection(this);
            end
            else
                `uvm_info(this.get_full_name(), "starting_phase null" , UVM_LOW)

            misc_if = refm.misc_if;


            //phase_done.set_drain_time(this, 0ns);
            wait(refm.misc_if.reset === 1);
            repeat(3)         @(posedge refm.misc_if.clock);
            ->refm.misc_if.initialed_evt;

            fork
                begin
                    fork
                        begin //axi slave sequence. loop delays
                            `uvm_create_on(axi_slave_gmem_w_seq, p_sequencer.gmem_w_sqr);
                            axi_slave_gmem_w_seq.misc_if = refm.misc_if;
                            axi_slave_gmem_w_seq.ap_done    = refm.ap_done_for_nexttrans   ;
                            axi_slave_gmem_w_seq.ap_ready   = refm.ap_ready_for_nexttrans  ;
                            axi_slave_gmem_w_seq.finish     = refm.finish ;
                            axi_slave_gmem_w_seq.isusr_delay = axi_pkg::NO_DELAY;
                            `uvm_send(axi_slave_gmem_w_seq);
                        end
                        begin //axi slave sequence. loop delays
                            `uvm_create_on(axi_slave_gmem_sw_seq, p_sequencer.gmem_sw_sqr);
                            axi_slave_gmem_sw_seq.misc_if = refm.misc_if;
                            axi_slave_gmem_sw_seq.ap_done    = refm.ap_done_for_nexttrans   ;
                            axi_slave_gmem_sw_seq.ap_ready   = refm.ap_ready_for_nexttrans  ;
                            axi_slave_gmem_sw_seq.finish     = refm.finish ;
                            axi_slave_gmem_sw_seq.isusr_delay = axi_pkg::NO_DELAY;
                            `uvm_send(axi_slave_gmem_sw_seq);
                        end
                        begin //axi slave sequence. loop delays
                            `uvm_create_on(axi_slave_gmem_x_seq, p_sequencer.gmem_x_sqr);
                            axi_slave_gmem_x_seq.misc_if = refm.misc_if;
                            axi_slave_gmem_x_seq.ap_done    = refm.ap_done_for_nexttrans   ;
                            axi_slave_gmem_x_seq.ap_ready   = refm.ap_ready_for_nexttrans  ;
                            axi_slave_gmem_x_seq.finish     = refm.finish ;
                            axi_slave_gmem_x_seq.isusr_delay = axi_pkg::NO_DELAY;
                            `uvm_send(axi_slave_gmem_x_seq);
                        end
                        begin //axi slave sequence. loop delays
                            `uvm_create_on(axi_slave_gmem_y_seq, p_sequencer.gmem_y_sqr);
                            axi_slave_gmem_y_seq.misc_if = refm.misc_if;
                            axi_slave_gmem_y_seq.ap_done    = refm.ap_done_for_nexttrans   ;
                            axi_slave_gmem_y_seq.ap_ready   = refm.ap_ready_for_nexttrans  ;
                            axi_slave_gmem_y_seq.finish     = refm.finish ;
                            axi_slave_gmem_y_seq.isusr_delay = axi_pkg::NO_DELAY;
                            `uvm_send(axi_slave_gmem_y_seq);
                        end
                        begin //axi slave sequence. loop delays
                            `uvm_create_on(axi_slave_gmem_meta_seq, p_sequencer.gmem_meta_sqr);
                            axi_slave_gmem_meta_seq.misc_if = refm.misc_if;
                            axi_slave_gmem_meta_seq.ap_done    = refm.ap_done_for_nexttrans   ;
                            axi_slave_gmem_meta_seq.ap_ready   = refm.ap_ready_for_nexttrans  ;
                            axi_slave_gmem_meta_seq.finish     = refm.finish ;
                            axi_slave_gmem_meta_seq.isusr_delay = axi_pkg::NO_DELAY;
                            `uvm_send(axi_slave_gmem_meta_seq);
                        end
                        begin
                            int control_page_idx_bak;
                            `uvm_create_on(axi_master_wr_control_seq, p_sequencer.control_sqr);
                            axi_master_wr_control_seq.misc_if = refm.misc_if;
                            axi_master_wr_control_seq.ap_done    = refm.ap_done_for_nexttrans   ;
                            axi_master_wr_control_seq.ap_ready   = refm.ap_ready_for_nexttrans  ;
                            axi_master_wr_control_seq.finish     = refm.finish ;
                            axi_master_wr_control_seq.isusr_delay = axi_pkg::NO_DELAY;
                            for(int i=0; i<7; i++) begin
                                logic[63:0] data64bit_w_packed[$];
                                logic[32-1:0] databusbit_w_packed[$];
                                logic[63:0] data64bit_sw[$];
                                logic[32-1:0] databusbit_sw[$];
                                logic[63:0] data64bit_xq[$];
                                logic[32-1:0] databusbit_xq[$];
                                logic[63:0] data64bit_sx[$];
                                logic[32-1:0] databusbit_sx[$];
                                logic[63:0] data64bit_y[$];
                                logic[32-1:0] databusbit_y[$];
                                logic[63:0] data64bit_meta[$];
                                logic[32-1:0] databusbit_meta[$];
                                logic[63:0] data64bit_t[$];
                                logic[32-1:0] databusbit_t[$];
                                logic[63:0] data64bit_n[$];
                                logic[32-1:0] databusbit_n[$];
                                logic[63:0] data64bit_k[$];
                                logic[32-1:0] databusbit_k[$];
                                logic[63:0] data64bit_w_bytes[$];
                                logic[32-1:0] databusbit_w_bytes[$];
                                logic[63:0] data64bit_sw_bytes[$];
                                logic[32-1:0] databusbit_sw_bytes[$];
                                logic[63:0] data64bit_x_bytes[$];
                                logic[32-1:0] databusbit_x_bytes[$];
                                logic[63:0] data64bit_sx_bytes[$];
                                logic[32-1:0] databusbit_sx_bytes[$];
                                logic[63:0] data64bit_y_bytes[$];
                                logic[32-1:0] databusbit_y_bytes[$];
                                logic[63:0] data64bit_meta_bytes[$];
                                logic[32-1:0] databusbit_meta_bytes[$];
                                logic[63:0] data64bit_job_id[$];
                                logic[32-1:0] databusbit_job_id[$];
                                logic[63:0] data64bit_abi_version[$];
                                logic[32-1:0] databusbit_abi_version[$];
                                data64bit_w_packed.delete(); databusbit_w_packed.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                for(int j=0; j < (64+32-1)/32; j++) begin
                                    data64bit_w_packed.push_back( ((refm.mem_blk_pages_gmem_w.maxi_bundlevar_offset["w_packed"]+refm.mem_blk_pages_gmem_w.page_ofst[refm.mem_blk_pages_gmem_w.rd_page_idx])>>(j*32)) & (2**32-1) );
                                end
                                foreach(data64bit_w_packed[s]) databusbit_w_packed[s]=data64bit_w_packed[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_w_packed, 0, 16, 1);
                                data64bit_sw.delete(); databusbit_sw.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                for(int j=0; j < (64+32-1)/32; j++) begin
                                    data64bit_sw.push_back( ((refm.mem_blk_pages_gmem_sw.maxi_bundlevar_offset["sw"]+refm.mem_blk_pages_gmem_sw.page_ofst[refm.mem_blk_pages_gmem_sw.rd_page_idx])>>(j*32)) & (2**32-1) );
                                end
                                foreach(data64bit_sw[s]) databusbit_sw[s]=data64bit_sw[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_sw, 0, 28, 1);
                                data64bit_xq.delete(); databusbit_xq.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                for(int j=0; j < (64+32-1)/32; j++) begin
                                    data64bit_xq.push_back( ((refm.mem_blk_pages_gmem_x.maxi_bundlevar_offset["xq"]+refm.mem_blk_pages_gmem_x.page_ofst[refm.mem_blk_pages_gmem_x.rd_page_idx])>>(j*32)) & (2**32-1) );
                                end
                                foreach(data64bit_xq[s]) databusbit_xq[s]=data64bit_xq[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_xq, 0, 40, 1);
                                data64bit_sx.delete(); databusbit_sx.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                for(int j=0; j < (64+32-1)/32; j++) begin
                                    data64bit_sx.push_back( ((refm.mem_blk_pages_gmem_x.maxi_bundlevar_offset["sx"]+refm.mem_blk_pages_gmem_x.page_ofst[refm.mem_blk_pages_gmem_x.rd_page_idx])>>(j*32)) & (2**32-1) );
                                end
                                foreach(data64bit_sx[s]) databusbit_sx[s]=data64bit_sx[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_sx, 0, 52, 1);
                                data64bit_y.delete(); databusbit_y.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                for(int j=0; j < (64+32-1)/32; j++) begin
                                    data64bit_y.push_back( ((refm.mem_blk_pages_gmem_y.maxi_bundlevar_offset["y"]+refm.mem_blk_pages_gmem_y.page_ofst[refm.mem_blk_pages_gmem_y.rd_page_idx])>>(j*32)) & (2**32-1) );
                                end
                                foreach(data64bit_y[s]) databusbit_y[s]=data64bit_y[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_y, 0, 64, 1);
                                data64bit_meta.delete(); databusbit_meta.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                for(int j=0; j < (64+32-1)/32; j++) begin
                                    data64bit_meta.push_back( ((refm.mem_blk_pages_gmem_meta.maxi_bundlevar_offset["meta"]+refm.mem_blk_pages_gmem_meta.page_ofst[refm.mem_blk_pages_gmem_meta.rd_page_idx])>>(j*32)) & (2**32-1) );
                                end
                                foreach(data64bit_meta[s]) databusbit_meta[s]=data64bit_meta[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_meta, 0, 76, 1);
                                data64bit_t.delete(); databusbit_t.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_t.tobusdata(data64bit_t, refm.mem_blk_pages_control_t.rd_page_idx, 32);
                                foreach(data64bit_t[s]) databusbit_t[s]=data64bit_t[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_t, 0, 88, 1);
                                data64bit_n.delete(); databusbit_n.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_n.tobusdata(data64bit_n, refm.mem_blk_pages_control_n.rd_page_idx, 32);
                                foreach(data64bit_n[s]) databusbit_n[s]=data64bit_n[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_n, 0, 96, 1);
                                data64bit_k.delete(); databusbit_k.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_k.tobusdata(data64bit_k, refm.mem_blk_pages_control_k.rd_page_idx, 32);
                                foreach(data64bit_k[s]) databusbit_k[s]=data64bit_k[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_k, 0, 104, 1);
                                data64bit_w_bytes.delete(); databusbit_w_bytes.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_w_bytes.tobusdata(data64bit_w_bytes, refm.mem_blk_pages_control_w_bytes.rd_page_idx, 32);
                                foreach(data64bit_w_bytes[s]) databusbit_w_bytes[s]=data64bit_w_bytes[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_w_bytes, 0, 112, 1);
                                data64bit_sw_bytes.delete(); databusbit_sw_bytes.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_sw_bytes.tobusdata(data64bit_sw_bytes, refm.mem_blk_pages_control_sw_bytes.rd_page_idx, 32);
                                foreach(data64bit_sw_bytes[s]) databusbit_sw_bytes[s]=data64bit_sw_bytes[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_sw_bytes, 0, 124, 1);
                                data64bit_x_bytes.delete(); databusbit_x_bytes.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_x_bytes.tobusdata(data64bit_x_bytes, refm.mem_blk_pages_control_x_bytes.rd_page_idx, 32);
                                foreach(data64bit_x_bytes[s]) databusbit_x_bytes[s]=data64bit_x_bytes[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_x_bytes, 0, 136, 1);
                                data64bit_sx_bytes.delete(); databusbit_sx_bytes.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_sx_bytes.tobusdata(data64bit_sx_bytes, refm.mem_blk_pages_control_sx_bytes.rd_page_idx, 32);
                                foreach(data64bit_sx_bytes[s]) databusbit_sx_bytes[s]=data64bit_sx_bytes[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_sx_bytes, 0, 148, 1);
                                data64bit_y_bytes.delete(); databusbit_y_bytes.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_y_bytes.tobusdata(data64bit_y_bytes, refm.mem_blk_pages_control_y_bytes.rd_page_idx, 32);
                                foreach(data64bit_y_bytes[s]) databusbit_y_bytes[s]=data64bit_y_bytes[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_y_bytes, 0, 160, 1);
                                data64bit_meta_bytes.delete(); databusbit_meta_bytes.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_meta_bytes.tobusdata(data64bit_meta_bytes, refm.mem_blk_pages_control_meta_bytes.rd_page_idx, 32);
                                foreach(data64bit_meta_bytes[s]) databusbit_meta_bytes[s]=data64bit_meta_bytes[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_meta_bytes, 0, 172, 1);
                                data64bit_job_id.delete(); databusbit_job_id.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_job_id.tobusdata(data64bit_job_id, refm.mem_blk_pages_control_job_id.rd_page_idx, 32);
                                foreach(data64bit_job_id[s]) databusbit_job_id[s]=data64bit_job_id[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_job_id, 0, 184, 1);
                                data64bit_abi_version.delete(); databusbit_abi_version.delete();
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=0;
                                refm.mem_blk_pages_control_abi_version.tobusdata(data64bit_abi_version, refm.mem_blk_pages_control_abi_version.rd_page_idx, 32);
                                foreach(data64bit_abi_version[s]) databusbit_abi_version[s]=data64bit_abi_version[s][32-1:0];
                                axi_master_wr_control_seq.StableAxiliteNoUpdate=1;
                                axi_master_wr_control_seq.datamerge_inavg(databusbit_abi_version, 0, 196, 1);
                                `uvm_send(axi_master_wr_control_seq);
                                refm.write_data_finish_control = 1;
                                `uvm_info("control data writting thread", $sformatf("%0dth(total 7): waiting for all write data finish event",i), UVM_LOW)
                                wait(refm.allaxilite_write_data_finish.triggered);
                                refm.write_data_finish_control = 0;
                                fork
                                    begin // configure start to enable DUT
                                        axi_master_wr_control_seq.wr_addr_data.push_back( (1<<0)+(0<<32) );
                                        `uvm_info("control start dut by axilite", $sformatf("%0dth(total 7): begin to set start bit",i), UVM_LOW)
                                        `uvm_send(axi_master_wr_control_seq);
                                    end // end of configuration loop
                                    begin
                                        `uvm_info("control wait for ap_ready for next trans", $sformatf("%0dth(total 7): begin to wait",i), UVM_LOW)
                                        wait(refm.dut2tb_ap_ready.triggered);
                                        wait(refm.ap_done_for_nexttrans.triggered);
                                        tb_apply_delay(DELAY_MAXI); //make sure mem incr_rd_page_idx is called first
                                    end
                                join
                            end
                        end
                        begin
                            for(int j=0; j<7; j=j+refm.ap_done_cnt) begin
                                wait(misc_if.dut2tb_ap_done_kernel == 1);
                                `uvm_info("test finish control", $sformatf("ap_done of kernel is triggered"), UVM_LOW)
                                @(posedge misc_if.clock);
                                fork
                                    forever begin
                                        `uvm_create_on(axi_master_poll_control_seq, p_sequencer.control_sqr);
                                        axi_master_poll_control_seq.isusr_delay = axi_pkg::NO_DELAY;
                                        axi_master_poll_control_seq.misc_if = refm.misc_if;
                                        axi_master_poll_control_seq.rd_addr.push_back(0);
                                        `uvm_send(axi_master_poll_control_seq)
                                        repeat(2) @(posedge misc_if.clock);
                                    end
                                    begin
                                        `uvm_info("test finish control", $sformatf("%0dth(total 7) ap_done_for_nexttrans begin to wait",j), UVM_LOW)
                                        @refm.dut2tb_ap_done;
                                    end
                                join_any
                                disable fork;
                                wait(refm.ap_ready_for_nexttrans.triggered);
                            end
                        end
                    join
                end

                begin
                    for(int j=0; j<7; j=j+refm.ap_done_cnt) @refm.ap_done_for_nexttrans;
                    `uvm_info(this.get_full_name(), "autotb finished", UVM_LOW)
                    -> refm.finish;
                    refm.misc_if.finished = 1;
                    @(posedge refm.misc_if.clock);
                    refm.misc_if.finished = 0;
                    @(posedge refm.misc_if.clock);
                    -> refm.misc_if.finished_evt;
                end
            join_any
            repeat(5) @(posedge refm.misc_if.clock); //5 cycles delay for finish stuff. 5 is haphazard value

            p_sequencer.gmem_w_sqr.stop_sequences();
            p_sequencer.gmem_sw_sqr.stop_sequences();
            p_sequencer.gmem_x_sqr.stop_sequences();
            p_sequencer.gmem_y_sqr.stop_sequences();
            p_sequencer.gmem_meta_sqr.stop_sequences();
            p_sequencer.control_sqr.stop_sequences();
            disable fork;
                                                                                                    
            starting_phase.drop_objection(this);                                                    
                                                                                                    
        endtask                                                                                     
    endclass                                                                                        
                                                                                                    
`endif                                                                                              
