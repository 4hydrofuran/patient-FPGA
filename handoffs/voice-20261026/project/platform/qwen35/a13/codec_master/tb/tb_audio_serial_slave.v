`timescale 1ns / 1ps
// 异步编解码器时钟及独立DMA源/汇，自检双声道末位与周期边界。
module tb_audio_serial_slave(output reg o_pass = 1'b0);
    reg i_clk = 0;
    reg i_rstn = 0;
    reg i_bclk = 1;
    reg i_lrclk = 1;
    reg i_adcdat = 0;
    reg [31:0] i_control = 0;
    reg [31:0] i_tx_tdata = 0;
    reg i_tx_tvalid = 0;
    reg i_tx_tlast = 0;
    reg i_rx_tready = 1;
    wire o_tx_tready;
    wire [31:0] o_rx_tdata;
    wire o_rx_tvalid;
    wire o_rx_tlast;
    wire o_dacdat;
    wire [31:0] o_status;
    wire o_irq;
    wire reg_rise;
    wire reg_fall;
    wire reg_channel;
    wire reg_sample;
    reg [31:0] reg_frames [0:1023];
    integer cnt_tx = 0;
    integer cnt_rx = 0;
    integer cnt_dac = 0;
    integer cnt_phase = 0;
    integer cnt_frame = 0;
    integer cnt_cycle = 0;
    integer cnt_dac_bits = 0;
    reg flag_source = 0;
    reg flag_check = 0;
    reg flag_bad_last = 0;
    reg flag_dac_locked = 0;
    reg reg_dac_channel = 1;
    reg [15:0] reg_dac_word = 0;
    reg [15:0] reg_dac_left = 0;
    reg [31:0] reg_hold_data = 0;
    reg reg_hold_last = 0;
    reg flag_hold = 0;
    reg reg_adc_bit = 0;
    integer cnt_previous_right = 0;

    audio_serial_slave audio_serial_slave_Inst_dut (
        .i_clk(i_clk), .i_rstn(i_rstn), .i_rise(reg_rise),
        .i_fall(reg_fall), .i_channel(reg_channel), .i_sample(reg_sample), .i_control(i_control),
        .i_s_axis_tdata(i_tx_tdata), .i_s_axis_tvalid(i_tx_tvalid),
        .i_s_axis_tlast(i_tx_tlast), .i_m_axis_tready(i_rx_tready),
        .o_s_axis_tready(o_tx_tready), .o_m_axis_tdata(o_rx_tdata),
        .o_m_axis_tvalid(o_rx_tvalid), .o_m_axis_tlast(o_rx_tlast),
        .o_dacdat(o_dacdat), .o_status(o_status), .o_irq(o_irq)
    );
    audio_input_sampler audio_input_sampler_Inst_async (
        .i_clk(i_clk), .i_rstn(i_rstn), .i_bclk(i_bclk),
        .i_lrclk(i_lrclk), .i_adcdat(i_adcdat), .o_rise(reg_rise),
        .o_fall(reg_fall), .o_channel(reg_channel), .o_sample(reg_sample)
    );

    always #5 i_clk = ~i_clk;
    always @(negedge i_clk) begin
        if (flag_source) begin
            i_tx_tdata = reg_frames[cnt_tx];
            i_tx_tvalid = 1;
            i_tx_tlast = flag_bad_last || ((cnt_tx % 256) == 255);
        end else begin
            i_tx_tvalid = 0;
            i_tx_tlast = 0;
        end
    end
    always @(posedge i_clk) begin
        cnt_cycle = cnt_cycle + 1;
        if (i_tx_tvalid && o_tx_tready) cnt_tx = cnt_tx + 1;
        if (flag_check && flag_hold) begin
            if (!o_rx_tvalid || o_rx_tdata !== reg_hold_data || o_rx_tlast !== reg_hold_last)
                $fatal(1, "RX changed under backpressure");
        end
        flag_hold = o_rx_tvalid && !i_rx_tready;
        reg_hold_data = o_rx_tdata;
        reg_hold_last = o_rx_tlast;
        if (flag_check && o_rx_tvalid && i_rx_tready) begin
            if (o_rx_tdata !== reg_frames[cnt_rx])
                $fatal(1, "RX frame %0d got %h wanted %h", cnt_rx, o_rx_tdata, reg_frames[cnt_rx]);
            if (o_rx_tlast !== ((cnt_rx % 256) == 255)) $fatal(1, "RX TLAST mismatch");
            cnt_rx = cnt_rx + 1;
        end
    end
    // 接收器只用外部线上位流重建DAC帧，不读被测设计的移位寄存器。
    always @(posedge i_bclk) begin
        #1;
        if (flag_check) begin
            if (flag_dac_locked) reg_dac_word = {reg_dac_word[14:0], o_dacdat};
            if (i_lrclk != reg_dac_channel) begin
                if (flag_dac_locked) begin
                    if (cnt_dac_bits != 15) $fatal(1, "DAC slot geometry");
                    if (!reg_dac_channel) reg_dac_left = reg_dac_word;
                    else begin
                        if ({reg_dac_word, reg_dac_left} !== reg_frames[cnt_dac])
                            $fatal(1, "DAC frame %0d got %h wanted %h", cnt_dac, {reg_dac_word, reg_dac_left}, reg_frames[cnt_dac]);
                        cnt_dac = cnt_dac + 1;
                    end
                end
                if (!i_lrclk) flag_dac_locked = 1;
                reg_dac_channel = i_lrclk;
                cnt_dac_bits = 0;
                reg_dac_word = 0;
            end else if (flag_dac_locked) cnt_dac_bits = cnt_dac_bits + 1;
        end
    end
    // LR延迟10..30ns并叠加ADC延迟，包含额外采样偏斜的数字压力模型。
    // 周期648..652ns使边沿相位走遍系统时钟；不是晶振实测频差。
    task codec_bit;
        input lr;
        input adc;
        input integer low_ns;
        integer skew_ns;
        integer period_ns;
        begin
            skew_ns = 10 + (cnt_cycle % 21);
            period_ns = 648 + (cnt_cycle % 5);
            i_bclk = 0;
            #(skew_ns) i_lrclk = lr;
            #7 i_adcdat = adc;
            #(low_ns - skew_ns - 7) i_bclk = 1;
            #(period_ns - low_ns);
        end
    endtask
    task stop_and_clear;
        begin
            flag_check = 0;
            flag_source = 0;
            i_control = 0;
            #200;
            i_control = 4;
            #100;
            i_control = 0;
            #100;
            if (o_irq || o_status[4:0] != 0 || o_dacdat != 0)
                $fatal(1, "STOP/clear failed");
        end
    endtask

    initial begin
        $readmemh("frames.hex", reg_frames);
        #103 i_rstn = 1;
        #400;
        flag_source = 1;
        i_control = 3;
        #207;
        for (cnt_phase = 0; cnt_phase < 16; cnt_phase = cnt_phase + 1)
            codec_bit(1, 0, 325);
        flag_check = 1;
        cnt_previous_right = 0;
        for (cnt_frame = 0; cnt_frame < 520; cnt_frame = cnt_frame + 1) begin
            for (cnt_phase = 0; cnt_phase < 32; cnt_phase = cnt_phase + 1) begin
                if (cnt_phase == 0) reg_adc_bit = cnt_previous_right;
                else if (cnt_phase <= 16) reg_adc_bit = reg_frames[cnt_frame][16 - cnt_phase];
                else reg_adc_bit = reg_frames[cnt_frame][48 - cnt_phase];
                codec_bit(cnt_phase >= 16, reg_adc_bit, 260 + ((cnt_frame + cnt_phase) % 131));
                i_rx_tready = ((cnt_phase % 5) != 3);
                if (o_irq) $fatal(1, "normal transfer fault %h", o_status);
            end
            cnt_previous_right = reg_frames[cnt_frame][16];
        end
        i_rx_tready = 1;
        codec_bit(0, cnt_previous_right, 325);
        #200;
        if (cnt_rx != 520 || cnt_dac != 520) $fatal(1, "counts RX=%0d DAC=%0d", cnt_rx, cnt_dac);
        stop_and_clear;
        i_control = 1;
        for (cnt_phase = 0; cnt_phase < 16; cnt_phase = cnt_phase + 1) codec_bit(1, 0, 325);
        codec_bit(0, 0, 325);
        #100;
        if (!o_status[2]) $fatal(1, "underrun not detected");
        stop_and_clear;
        i_control = 2;
        #700000;
        if (!o_status[0]) $fatal(1, "missing clock not detected");
        i_control = 6;
        #500;
        if (!o_status[0]) $fatal(1, "running clear bypassed sticky fault");
        stop_and_clear;
        i_control = 2;
        for (cnt_phase = 0; cnt_phase < 16; cnt_phase = cnt_phase + 1) codec_bit(1, 0, 325);
        for (cnt_phase = 0; cnt_phase < 20; cnt_phase = cnt_phase + 1) codec_bit(0, 0, 325);
        #100;
        if (!o_status[1]) $fatal(1, "bad slot not detected");
        stop_and_clear;
        i_rx_tready = 0;
        i_control = 2;
        for (cnt_phase = 0; cnt_phase < 16; cnt_phase = cnt_phase + 1) codec_bit(1, 0, 325);
        cnt_previous_right = 0;
        for (cnt_frame = 0; cnt_frame < 3; cnt_frame = cnt_frame + 1) begin
            for (cnt_phase = 0; cnt_phase < 32; cnt_phase = cnt_phase + 1) begin
                if (cnt_phase == 0) reg_adc_bit = cnt_previous_right;
                else if (cnt_phase <= 16) reg_adc_bit = reg_frames[cnt_frame][16 - cnt_phase];
                else reg_adc_bit = reg_frames[cnt_frame][48 - cnt_phase];
                codec_bit(cnt_phase >= 16, reg_adc_bit, 325);
            end
            cnt_previous_right = reg_frames[cnt_frame][16];
        end
        codec_bit(0, cnt_previous_right, 325);
        if (!o_status[3] || !o_rx_tvalid || o_rx_tdata !== reg_frames[0])
            $fatal(1, "overrun or retained payload not correct");
        #300;
        if (!o_rx_tvalid || o_rx_tdata !== reg_frames[0]) $fatal(1, "fault changed stalled payload");
        i_rx_tready = 1;
        #200;
        if (o_rx_tvalid) $fatal(1, "faulted stream did not finish outstanding handshake");
        stop_and_clear;
        // 任意左半帧开启采集，不得把当前LR电平当新边界。
        i_lrclk = 0;
        #500;
        i_control = 2;
        for (cnt_phase = 0; cnt_phase < 4; cnt_phase = cnt_phase + 1) codec_bit(0, 0, 325);
        for (cnt_phase = 0; cnt_phase < 16; cnt_phase = cnt_phase + 1) codec_bit(1, 0, 325);
        for (cnt_phase = 0; cnt_phase < 32; cnt_phase = cnt_phase + 1) codec_bit(cnt_phase >= 16, 0, 325);
        i_rx_tready = 0;
        codec_bit(0, 0, 325);
        if (o_irq || !o_rx_tvalid || o_rx_tdata !== 32'h00000000) $fatal(1, "mid-frame start/resync failed");
        i_rx_tready = 1;
        stop_and_clear;
        // 播放单向也必须监视LR槽宽，不能依赖RX使能。
        cnt_tx = 0;
        flag_source = 1;
        i_control = 1;
        for (cnt_phase = 0; cnt_phase < 16; cnt_phase = cnt_phase + 1) codec_bit(1, 0, 325);
        for (cnt_phase = 0; cnt_phase < 20; cnt_phase = cnt_phase + 1) codec_bit(0, 0, 325);
        if (!o_status[1]) $fatal(1, "playback-only slot monitor failed");
        stop_and_clear;
        // 运行中异步断言复位，所有对外所有权和DAC都必须归零。
        cnt_tx = 0;
        flag_source = 1;
        i_control = 3;
        for (cnt_phase = 0; cnt_phase < 16; cnt_phase = cnt_phase + 1) codec_bit(1, 0, 325);
        codec_bit(0, 0, 325);
        i_rstn = 0;
        #50;
        if (o_dacdat || o_rx_tvalid || o_tx_tready || o_irq) $fatal(1, "active reset did not isolate stream");
        i_control = 0;
        flag_source = 0;
        i_rstn = 1;
        #300;
        stop_and_clear;
        flag_source = 1;
        flag_bad_last = 1;
        cnt_tx = 0;
        i_control = 1;
        #500;
        if (!o_status[4]) $fatal(1, "bad TLAST not detected");
        stop_and_clear;
        o_pass = 1'b1;
        $display("VERILOG-GEN-RESULT PASS duplex_frames=520 periods=2 fault_cases=5 extra_checks=4");
        $finish;
    end
    initial begin
        #30000000;
        $fatal(1, "simulation timeout");
    end
endmodule
