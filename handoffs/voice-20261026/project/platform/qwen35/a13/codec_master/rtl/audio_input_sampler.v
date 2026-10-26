`timescale 1ns / 1ps

////////////////////////////////////English///////////////////////////////////////
// Company:         Erie
// Engineer:        Erie
//
// Create Date:     2026/10/25 10:21:16
// Design Name:     audio_input_sampler
// Module Name:     audio_input_sampler
// Description:     description/audio_input_sampler_Design.pdf
// Simulations:     testbench/vivado/2021.1/audio_input_sampler
//
// Referrences:     None
//
// Dependencies:    None
//
// Version:         V1.0
// Revision Date:   2026/10/25 10:21:16
// History:
// Time             Version     Revised by        Contents
// 2026/10/25       V1.0        Erie              Create file.
///////////////////////////////////Chinese////////////////////////////////////////
// 版权归属:        Erie
// 开发人员:        Erie
//
// 创建日期:        2026年10月25日
// 设计名称:        audio_input_sampler
// 模块名称:        audio_input_sampler
// 模块说明:        Description/audio_input_sampler_Design.pdf
// 仿真工程:        TestBench/Vivado/2021.1/audio_input_sampler
//
// 参考资料:        None
//
// 依赖文件:        None
//
// 当前版本:        V1.0
// 修订日期:        2026年10月25日
// 修订历史:
// 时间             版本        修订人            修订内容
// 2026年10月25日   V1.0        Erie              创建文件

module audio_input_sampler
(
	//-----------------全局信号-----------------//
	input i_clk,                                // 系统过采样时钟
	input i_rstn,                               // 专用复位IP的低有效输出

	//-----------------用户接口-----------------//
	input i_bclk,                               // 编解码器位时钟，仅作为异步数据
	input i_lrclk,                              // 编解码器左右声道标记
	input i_adcdat,                             // 编解码器录音串行数据
	output o_rise,                              // 延迟后的位时钟上升事件
	output o_fall,                              // 延迟后的位时钟下降事件
	output o_channel,                           // 已同步的左右声道电平
	output o_sample                             // 已同步的录音位值
);

	//----------------寄存器信号----------------//
	//外部串行电平与边沿稳定流水
	(* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *) reg [2:0]reg_bclk_sync = 3'b000; // 位时钟三级亚稳态隔离
	(* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *) reg [2:0]reg_lrclk_sync = 3'b000; // 声道标记三级隔离
	(* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *) reg [2:0]reg_adc_sync = 3'b000; // ADC位三级隔离
	reg [3:0]reg_bclk_delay = 4'b0000;          // 四拍等待覆盖声道传播与跨链采样偏斜
	reg reg_bclk_previous = 1'b0;               // 延迟位时钟的前次电平

	//-----------------输出信号-----------------//
	//用户接口
	reg rise_o = 1'b0;                          // 上升沿单系统拍事件寄存
	reg fall_o = 1'b0;                          // 下降沿单系统拍事件寄存
	reg channel_o = 1'b0;                       // 对外稳定的声道标记
	reg sample_o = 1'b0;                        // 对外稳定的输入数据

	//---------------输出信号连线---------------//
	//用户接口
	assign o_rise = rise_o;                     // 向串行接收逻辑交付采样事件
	assign o_fall = fall_o;                     // 向串行发送逻辑交付更新事件
	assign o_channel = channel_o;               // 交付延迟边沿之前已稳定的LR值
	assign o_sample = sample_o;                 // 交付在高相采样的ADC值

	//-------------输出信号处理区域-------------//
	//用户接口
	// 上升脉冲只持续一个系统周期。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			rise_o <= 1'b0;                     // 取消复位时的虚假上升事件
		end else begin
			rise_o <= reg_bclk_delay[3] & ~reg_bclk_previous; // 高相入口事件
		end
	end

	// 下降事件用于在下一采样沿前更新DAC输出。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			fall_o <= 1'b0;                     // 取消复位时的虚假下降事件
		end else begin
			fall_o <= ~reg_bclk_delay[3] & reg_bclk_previous; // 低相入口事件
		end
	end

	// 声道输出只取隔离链的最后一级。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			channel_o <= 1'b0;                  // 对外声道初值归左
		end else begin
			channel_o <= reg_lrclk_sync[2];     // 提供重汇合前稳定电平
		end
	end

	// 输入位输出在系统域寄存。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			sample_o <= 1'b0;                   // ADC隔离输出初始无有效位
		end else begin
			sample_o <= reg_adc_sync[2];        // 隔离外部ADC扇出
		end
	end

	//-------------主要任务处理区域-------------//
	// 捕获原始位时钟，不驱动任何时钟引脚。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_bclk_sync <= 3'b000;            // 清空三个位时钟隔离级
		end else begin
			reg_bclk_sync <= {reg_bclk_sync[1:0], i_bclk}; // 单向移动异步电平
		end
	end

	// 声道标记使用与数据相同长度的同步链。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_lrclk_sync <= 3'b000;           // 清空声道标记隔离状态
		end else begin
			reg_lrclk_sync <= {reg_lrclk_sync[1:0], i_lrclk}; // 消除直接异步逻辑扇出
		end
	end

	// ADC在延迟上升事件前已经过三级隔离。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_adc_sync <= 3'b000;             // 清除未同步的录音位历史
		end else begin
			reg_adc_sync <= {reg_adc_sync[1:0], i_adcdat}; // 保持串行位电平顺序
		end
	end

	// 只延迟事件路径，避免LR与BCLK各自同步后立即重汇合。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_bclk_delay <= 4'b0000;          // 重汇合等待流水清空
		end else begin
			reg_bclk_delay <= {reg_bclk_delay[2:0], reg_bclk_sync[2]}; // 事件滞后数据四拍
		end
	end

	// 保存边沿判断所需的历史电平。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_bclk_previous <= 1'b0;          // 前次位时钟不产生启动边沿
		end else begin
			reg_bclk_previous <= reg_bclk_delay[3]; // 对齐延迟链末级
		end
	end

endmodule
