`timescale 1ns / 1ps

////////////////////////////////////English///////////////////////////////////////
// Company:         Erie
// Engineer:        Erie
//
// Create Date:     2026/10/25 10:51:02
// Design Name:     audio_serial_slave
// Module Name:     audio_serial_slave
// Description:     description/audio_serial_slave_Design.pdf
// Simulations:     testbench/vivado/2021.1/audio_serial_slave
//
// Referrences:     None
//
// Dependencies:    None
//
// Version:         V1.0
// Revision Date:   2026/10/25 10:51:02
// History:
// Time             Version     Revised by        Contents
// 2026/10/25       V1.0        Erie              Create file.
///////////////////////////////////Chinese////////////////////////////////////////
// 版权归属:        Erie
// 开发人员:        Erie
//
// 创建日期:        2026年10月25日
// 设计名称:        audio_serial_slave
// 模块名称:        audio_serial_slave
// 模块说明:        Description/audio_serial_slave_Design.pdf
// 仿真工程:        TestBench/Vivado/2021.1/audio_serial_slave
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

module audio_serial_slave
(
	//-----------------全局信号-----------------//
	(* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 i_clk CLK", X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF S_AXIS:M_AXIS, ASSOCIATED_RESET i_rstn, FREQ_HZ 99999001" *) input i_clk, // 唯一工作时钟
	(* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 i_rstn RST", X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *) input i_rstn, // 专用控制器低有效复位

	//-----------------用户接口-----------------//
	input i_rise,                               // 同域位上升单拍事件
	input i_fall,                               // 同域位下降单拍事件
	input i_channel,                            // 延迟事件之前稳定的LR电平
	input i_sample,                             // 延迟事件之前稳定的录音位
	input [31:0]i_control,                      // TX、RX及停止后故障确认
	output o_dacdat,                            // 低相更新的串行播放位
	output [31:0]o_status,                      // 签名、对齐及锁存故障
	output o_irq,                               // 保持型故障中断

	//-------------AXI-Stream总线S--------------//
	//数据通道
	(* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TDATA" *) input [31:0]i_s_axis_tdata, // 完整立体声帧，低半字左声道

	//控制通道
	(* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TVALID" *) input i_s_axis_tvalid, // MM2S持有有效播放负载
	(* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TLAST" *) input i_s_axis_tlast, // 每256帧的发送包尾
	(* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TREADY" *) output o_s_axis_tready, // 播放预取许可

	//-------------AXI-Stream总线M--------------//
	//数据通道
	(* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TDATA" *) output [31:0]o_m_axis_tdata, // 完整录音帧，高半字右声道

	//控制通道
	(* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TREADY" *) input i_m_axis_tready, // 内存端允许释放当前录音帧
	(* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TVALID" *) output o_m_axis_tvalid, // S2MM待收负载有效
	(* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TLAST" *) output o_m_axis_tlast // 与录音负载绑定的包尾
);

	//---------------配置参数区域---------------//
	//cmd参数
	localparam [2:0]CMD_IDLE = 3'b000;          // 当前系统拍无音频位操作
	localparam [2:0]CMD_ZERO = 3'b001;          // 清除当前串行内容
	localparam [2:0]CMD_LEFT = 3'b010;          // 发送装左字，接收完成左字
	localparam [2:0]CMD_RIGHT = 3'b011;         // 发送装右字，接收完成右字
	localparam [2:0]CMD_SHIFT = 3'b100;         // 声道内推进一位

	//-----------------计数信号-----------------//
	reg [7:0]cnt_tx_period = 8'h00;             // 已接收的包内帧序号
	reg [4:0]cnt_rx_bits = 5'b00000;            // 边界之前收到的位数
	reg [7:0]cnt_rx_period = 8'h00;             // 已存入缓存的录音包内帧序号
	reg [15:0]cnt_watchdog = 16'h0000;          // 无位事件的系统拍年龄

	//----------------寄存器信号----------------//
	reg [2:0]reg_tx_command = 3'b001;           // 下降事件寄存译码
	reg [2:0]reg_rx_command = 3'b001;           // 上升事件寄存译码
	reg reg_tx_channel = 1'b0;                  // 前次下降事件的声道标记
	reg reg_rx_channel = 1'b0;                  // 前次上升事件的声道标记
	reg [31:0]reg_tx_frame = 32'h00000000;      // 单帧播放预取区
	reg [15:0]reg_tx_shift = 16'h0000;          // 当前待发声道
	reg [15:0]reg_tx_right = 16'h0000;          // 同帧右字配对暂存
	reg [15:0]reg_rx_shift = 16'h0000;          // 当前接收声道半字
	reg [15:0]reg_rx_left = 16'h0000;           // 完整左字等待右字
	reg [15:0]reg_rx_right = 16'h0000;          // 右字完成与入缓存之间的暂存
	reg [4:0]reg_fault = 5'b00000;              // 五种错误统一锁存字

	//-----------------标志信号-----------------//
	reg flag_tx_enable = 1'b0;                  // 寄存后的无故障播放许可
	reg flag_monitor_enable = 1'b0;             // 任一路运行即监视帧几何
	reg flag_ack_errors = 1'b0;                 // 停机后的故障确认命令
	reg flag_tx_pending = 1'b0;                 // 缓存持有尚未播放的帧
	reg flag_tx_started = 1'b0;                 // 已在左边界开始首帧
	reg flag_rx_locked = 1'b0;                  // 已找到真实右到左边界
	reg flag_rx_space = 1'b0;                   // 提前预译码录音缓存空间
	reg flag_rx_store = 1'b0;                   // 设备整帧入缓存单拍指令
	reg flag_last_bit = 1'b0;                   // 槽内已有15个普通位
	reg flag_tx_last = 1'b0;                    // 下一播放帧应携带TLAST
	reg flag_rx_boundary = 1'b0;                // 声道收尾指令延迟标记
	reg flag_rx_shift = 1'b0;                   // 普通采样指令延迟标记
	reg flag_check_geometry = 1'b0;             // 与指令对齐的先前帧锁定状态
	reg flag_slot_early = 1'b0;                 // LR提前切换事件
	reg flag_slot_late = 1'b0;                  // LR滞后切换事件
	reg flag_timeout = 1'b0;                    // 失钟计数到达饱和
	reg flag_underrun = 1'b0;                   // 消费点无播放帧事件
	reg flag_overrun = 1'b0;                    // 录音帧未及时释放事件
	reg flag_bad_packet = 1'b0;                 // MM2S包尾位置错误事件

	//-----------------其他信号-----------------//
	//串流事件与计数中间量
	wire tx_accept;                             // 播放总线成功移交事件
	wire tx_consume;                            // 设备左边界唯一消费点
	wire rx_accept;                             // 内存端确认当前录音负载
	wire rx_complete;                           // 已锁定帧的右字收尾
	wire rx_changed;                            // 稳定LR与前次采样的差异
	wire [15:0]rx_word;                         // 当前声道补入末位后的内容
	wire [8:0]tx_increment;                     // 保留进位的发送周期加法
	wire [8:0]rx_increment;                     // 保留进位的接收周期加法
	wire [5:0]bits_increment;                   // 保留进位的槽宽加法
	wire [16:0]watchdog_increment;              // 全精度失钟年龄加法
	wire bit_edge;                              // 任一外部位事件
	wire slot_error;                            // 两种帧几何异常合并
	wire watchdog_full;                         // 当前计数已到饱和，不能等延迟比较结果

	//-----------------输出信号-----------------//
	//用户接口
	reg dacdat_o = 1'b0;                        // 仅发送指令可以更新的位值
	reg [31:0]status_o = 32'ha13c0000;          // CPU同域状态快照
	reg irq_o = 1'b0;                           // 故障聚合注册输出

	//AXI-Stream总线S--控制通道
	reg s_axis_tready_o = 1'b0;                 // 立即撤销的注册播放许可

	//AXI-Stream总线M--数据通道
	reg [31:0]m_axis_tdata_o = 32'h00000000;    // 回压期间保持的录音负载

	//AXI-Stream总线M--控制通道
	reg m_axis_tvalid_o = 1'b0;                 // 录音缓存对外所有权
	reg m_axis_tlast_o = 1'b0;                  // 回压期间保持的录音包尾

	//---------------其他信号连线---------------//
	//其他信号连线
	assign tx_accept = i_s_axis_tvalid & s_axis_tready_o; // 双方同意才接收播放帧
	assign tx_consume = (reg_tx_command == CMD_LEFT); // 装左字即移交当前帧
	assign rx_accept = m_axis_tvalid_o & i_m_axis_tready; // 内存确认才释放录音负载
	assign rx_complete = (reg_rx_command == CMD_RIGHT) & flag_rx_locked; // 右字末位代表完整帧
	assign rx_changed = (i_channel != reg_rx_channel); // 只比较已同步稳定电平
	assign rx_word = {reg_rx_shift[14:0], i_sample}; // 边界拍LSB归前一声道
	assign tx_increment = {1'b0, cnt_tx_period} + 9'b000000001; // 保留第256帧进位
	assign rx_increment = {1'b0, cnt_rx_period} + 9'b000000001; // 录音包索引全精度增量
	assign bits_increment = {1'b0, cnt_rx_bits} + 6'b000001; // 显式保留槽位进位
	assign watchdog_increment = {1'b0, cnt_watchdog} + 17'b00000000000000001; // 饱和前的全宽年龄
	assign bit_edge = i_rise | i_fall;          // 只刷新看门狗，不生成采样节拍
	assign slot_error = flag_slot_early | flag_slot_late; // 合并独立预译码的异常
	assign watchdog_full = (cnt_watchdog == 16'hffff); // 饱和控制使用本拍值，避免多加一拍回绕

	//---------------输出信号连线---------------//
	//用户接口
	assign o_dacdat = dacdat_o;                 // 唯一DAC线驱动寄存器
	assign o_status = status_o;                 // CPU读取统一快照
	assign o_irq = irq_o;                       // 故障电平保持到确认

	//AXI-Stream总线S--控制通道
	assign o_s_axis_tready = s_axis_tready_o;   // 播放许可桥接MM2S

	//AXI-Stream总线M--数据通道
	assign o_m_axis_tdata = m_axis_tdata_o;     // 录音寄存负载桥接S2MM

	//AXI-Stream总线M--控制通道
	assign o_m_axis_tvalid = m_axis_tvalid_o;   // 当前帧直到握手才释放
	assign o_m_axis_tlast = m_axis_tlast_o;     // 包尾与负载共同持有

	//-------------输出信号处理区域-------------//
	//用户接口
	// 数字零不等价于模拟静音；本候选不允许试音。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			dacdat_o <= 1'b0;                   // 外部DAC输入初始低电平
		end else begin
			case(reg_tx_command)
				CMD_ZERO:begin
					dacdat_o <= 1'b0;           // 停止或故障输出零位
				end
				CMD_IDLE:begin
					dacdat_o <= dacdat_o;       // 保持到下一低相更新
				end
				default:begin
					dacdat_o <= reg_tx_shift[15]; // 读取旧字保留I2S一位延迟
				end
			endcase
		end
	end

	// 固定A13C识别码与采集锁定、播放状态组成GPIO诊断字。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			status_o <= 32'ha13c0000;           // 复位仍提供新接口身份
		end else begin
			status_o <= {16'ha13c, 8'h00, flag_rx_locked, flag_tx_started, irq_o, reg_fault}; // 同域诊断快照
		end
	end

	// 五位诊断字归约后形成持续高电平，供PS中断控制器接收。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			irq_o <= 1'b0;                      // 初始无中断请求
		end else begin
			irq_o <= |reg_fault;                // 故障保持型聚合中断
		end
	end

	//AXI-Stream总线S--控制通道
	// 接受拍立即撤销ready，不能延迟一拍重复接受。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			s_axis_tready_o <= 1'b0;            // 初始无DMA预取许可
		end else begin
			case({flag_tx_enable, tx_accept, tx_consume})
				3'b100:begin
					s_axis_tready_o <= ~flag_tx_pending; // 缓存空时保持许可
				end
				3'b101:begin
					s_axis_tready_o <= 1'b1;    // 设备消费后允许下一帧
				end
				default:begin
					s_axis_tready_o <= 1'b0;    // 接受、停止或异常同时事件撤销许可
				end
			endcase
		end
	end

	//AXI-Stream总线M--数据通道
	// 只有新整帧或软件STOP可以改变对外负载。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			m_axis_tdata_o <= 32'h00000000;     // 初始录音负载全零
		end else if(!i_control[1])begin
			m_axis_tdata_o <= 32'h00000000;     // STOP丢弃旧窗口数据
		end else if(flag_rx_store == 1'b1)begin
			m_axis_tdata_o <= {reg_rx_right, reg_rx_left}; // 同帧左右字按内存顺序打包
		end
	end

	//AXI-Stream总线M--控制通道
	//录音缓存所有权
	// 缓存占用由真握手释放；下游暂停时维持VALID高电平。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			m_axis_tvalid_o <= 1'b0;            // 初始无待收负载
		end else begin
			case({i_control[1], rx_accept, flag_rx_store})
				3'b100:begin
					m_axis_tvalid_o <= m_axis_tvalid_o; // 等待内存端接收当前帧
				end
				3'b101:begin
					m_axis_tvalid_o <= 1'b1;    // 当前帧取得录音缓存所有权
				end
				default:begin
					m_axis_tvalid_o <= 1'b0;    // STOP或真实接收后释放
				end
			endcase
		end
	end

	// 包尾随负载一同寄存，反压期间不能用组合计数替代。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			m_axis_tlast_o <= 1'b0;             // 初始没有录音包尾
		end else if(!i_control[1])begin
			m_axis_tlast_o <= 1'b0;             // 停止清除前一包尾
		end else if(flag_rx_store == 1'b1)begin
			m_axis_tlast_o <= (cnt_rx_period == 8'hff); // 第256帧对应当前包尾
		end
	end

	//-------------主要任务处理区域-------------//
	// 故障反馈在短寄存许可路径上切断。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_tx_enable <= 1'b0;             // 初始禁止播放消费
		end else begin
			flag_tx_enable <= i_control[0] & ~irq_o; // 单路使能且无故障
		end
	end

	// 单向播放也必须检测帧几何，不依赖采集是否开启。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_monitor_enable <= 1'b0;        // 初始不接受音频事件
		end else begin
			flag_monitor_enable <= (|i_control[1:0]) & ~irq_o; // 任一路启用即监视
		end
	end

	// 软件只有在两路停止后才能确认锁存错误。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_ack_errors <= 1'b0;            // 不把复位当软件命令
		end else begin
			flag_ack_errors <= i_control[2] & ~(|i_control[1:0]); // 拒绝运行中清错
		end
	end

	// 固定输入译码寄存为指令，不由指令自身反馈转移。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_tx_command <= CMD_ZERO;         // 初始清除串行发送内容
		end else begin
			case({flag_tx_enable, i_fall, reg_tx_channel, i_channel})
				4'b1000, 4'b1001, 4'b1010, 4'b1011:begin
					reg_tx_command <= CMD_IDLE; // 等待下一下降事件
				end
				4'b1100, 4'b1111:begin
					reg_tx_command <= CMD_SHIFT; // 相同声道内推进一位
				end
				4'b1101:begin
					reg_tx_command <= CMD_RIGHT; // 左到右边界装右字
				end
				4'b1110:begin
					reg_tx_command <= CMD_LEFT; // 右到左边界消费新帧
				end
				default:begin
					reg_tx_command <= CMD_ZERO; // 禁流持续清空
				end
			endcase
		end
	end

	// 接收译码先判断边界，执行时才把当前位归入旧声道。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_rx_command <= CMD_ZERO;         // 初始化不认可半帧
		end else begin
			case({flag_monitor_enable, i_rise, rx_changed, i_channel})
				4'b1000, 4'b1001, 4'b1010, 4'b1011:begin
					reg_rx_command <= CMD_IDLE; // 高相入口尚未到达
				end
				4'b1100, 4'b1101:begin
					reg_rx_command <= CMD_SHIFT; // 同声道收入下一位
				end
				4'b1111:begin
					reg_rx_command <= CMD_LEFT; // 新LR为右时完成旧左字
				end
				4'b1110:begin
					reg_rx_command <= CMD_RIGHT; // 新LR为左时完成旧右字
				end
				default:begin
					reg_rx_command <= CMD_ZERO; // 无许可时丢弃串行半字
				end
			endcase
		end
	end

	// 发送声道历史仅在真实下降事件更新。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_tx_channel <= 1'b0;             // 历史初始为左电平
		end else if(i_fall == 1'b1)begin
			reg_tx_channel <= i_channel;        // 登记已稳定的当前LR
		end
	end

	// 停机跟踪LR，重启不会把静态左电平误当新边界。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_rx_channel <= 1'b0;             // 接收历史初始归左
		end else if(flag_monitor_enable == 1'b0)begin
			reg_rx_channel <= i_channel;        // 未运行时观察真实声道电平
		end else if(i_rise == 1'b1)begin
			reg_rx_channel <= i_channel;        // 上升事件后登记新声道
		end
	end

	// 单帧缓存仅写入真正完成MM2S握手的负载。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_tx_frame <= 32'h00000000;       // 预取区初始无旧内容
		end else if(!i_control[0])begin
			reg_tx_frame <= 32'h00000000;       // STOP不重播上一窗口帧
		end else if(tx_accept == 1'b1)begin
			reg_tx_frame <= i_s_axis_tdata;     // 完整ready-valid移交
		end
	end

	// 缓存所有权的三个动作采用单个短译码处理。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_tx_pending <= 1'b0;            // 初始不持有播放帧
		end else begin
			case({i_control[0], tx_consume, tx_accept})
				3'b100:begin
					flag_tx_pending <= flag_tx_pending; // 无移交时保持所有权
				end
				3'b101:begin
					flag_tx_pending <= 1'b1;    // DMA交付一帧待发负载
				end
				default:begin
					flag_tx_pending <= 1'b0;    // 停机或左起点释放缓存
				end
			endcase
		end
	end

	// 左起点已有预取数据才能建立播放对齐。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_tx_started <= 1'b0;            // 尚未开始首帧
		end else begin
			case(reg_tx_command)
				CMD_ZERO:begin
					flag_tx_started <= 1'b0;    // 停止撤销对齐状态
				end
				CMD_LEFT:begin
					flag_tx_started <= flag_tx_pending; // 首帧需要预取所有权
				end
				default:begin
					flag_tx_started <= flag_tx_started; // 普通位不改变帧对齐
				end
			endcase
		end
	end

	// 右字与当前左字绑定，不能从下一帧重新取数。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_tx_right <= 16'h0000;           // 配对右字初始静默
		end else begin
			case(reg_tx_command)
				CMD_ZERO:begin
					reg_tx_right <= 16'h0000;   // 停机清除右字历史
				end
				CMD_LEFT:begin
					reg_tx_right <= reg_tx_frame[31:16]; // 暂存同帧右样本
				end
				default:begin
					reg_tx_right <= reg_tx_right; // 配对保持到下个左起点
				end
			endcase
		end
	end

	// 边界装下一字，独立输出过程同拍仍读旧字LSB。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_tx_shift <= 16'h0000;           // 初始移位字全零
		end else begin
			case(reg_tx_command)
				CMD_ZERO:begin
					reg_tx_shift <= 16'h0000;   // 禁流丢弃未发声道
				end
				CMD_LEFT:begin
					reg_tx_shift <= reg_tx_frame[15:0]; // 下一下降事件才发左MSB
				end
				CMD_RIGHT:begin
					reg_tx_shift <= reg_tx_right; // 下一下降事件才发右MSB
				end
				CMD_SHIFT:begin
					reg_tx_shift <= {reg_tx_shift[14:0], 1'b0}; // 当前字按MSB次序移出
				end
				default:begin
					reg_tx_shift <= reg_tx_shift; // 系统空拍不移动音频位
				end
			endcase
		end
	end

	// 明确保留加法进位后截低八位，实现固定模256周期。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			cnt_tx_period <= 8'h00;             // 播放包从首帧开始
		end else begin
			case({i_control[0], tx_accept})
				2'b10:begin
					cnt_tx_period <= cnt_tx_period; // 等待设备释放预取空间
				end
				2'b11:begin
					cnt_tx_period <= tx_increment[7:0]; // 第256帧后开始新包
				end
				default:begin
					cnt_tx_period <= 8'h00;     // STOP撤销旧包进度
				end
			endcase
		end
	end

	// 接收边界当前位已在rx_word中，收尾后清空半字。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_rx_shift <= 16'h0000;           // 初始没有录音半字
		end else begin
			case(reg_rx_command)
				CMD_IDLE:begin
					reg_rx_shift <= reg_rx_shift; // 非采样拍保持声道内容
				end
				CMD_SHIFT:begin
					reg_rx_shift <= rx_word;    // 收入当前声道下一位
				end
				default:begin
					reg_rx_shift <= 16'h0000;   // 边界或停止后重新收字
				end
			endcase
		end
	end

	// 完整左字等待同帧右字期间不改变。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_rx_left <= 16'h0000;            // 左字初始无历史样本
		end else begin
			case(reg_rx_command)
				CMD_ZERO:begin
					reg_rx_left <= 16'h0000;    // 不跨运行窗口配对
				end
				CMD_LEFT:begin
					reg_rx_left <= rx_word;     // 左到右边界完成旧左字
				end
				default:begin
					reg_rx_left <= reg_rx_left; // 右字完成前保持同帧左字
				end
			endcase
		end
	end

	// 第一真实右到左转换建立完整帧起点。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_rx_locked <= 1'b0;             // 启动后等待一次右字收尾
		end else begin
			case(reg_rx_command)
				CMD_ZERO:begin
					flag_rx_locked <= 1'b0;     // 停止必须重新找左起点
				end
				CMD_RIGHT:begin
					flag_rx_locked <= 1'b1;     // 新LR为左时开始完整帧
				end
				default:begin
					flag_rx_locked <= flag_rx_locked; // 帧内位维持锁定
				end
			endcase
		end
	end

	// 非边界十五位之后，下一采样必须是边界LSB。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			cnt_rx_bits <= 5'b00000;            // 槽位序初始清零
		end else begin
			case(reg_rx_command)
				CMD_IDLE:begin
					cnt_rx_bits <= cnt_rx_bits; // 空系统拍不计音频位
				end
				CMD_SHIFT:begin
					cnt_rx_bits <= bits_increment[4:0]; // 真实位事件推进序号
				end
				default:begin
					cnt_rx_bits <= 5'b00000;    // 收尾或停机重新计位
				end
			endcase
		end
	end

	// 槽末比较提前寄存，降低后续几何检查路径。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_last_bit <= 1'b0;              // 尚未收到十五个普通位
		end else begin
			flag_last_bit <= (cnt_rx_bits == 5'b01111); // 当前字等待边界末位
		end
	end

	// 单帧弹性预取之间至少相隔设备帧时间，包尾比较可提前寄存。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_tx_last <= 1'b0;               // 包首不应携带TLAST
		end else begin
			flag_tx_last <= (cnt_tx_period == 8'hff); // 第256个接受帧应为包尾
		end
	end

	// 提前记录空间，负载不会因为DMA回压而被覆盖。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_rx_space <= 1'b0;              // 初始不开放录音缓存
		end else begin
			flag_rx_space <= ~m_axis_tvalid_o & i_control[1]; // 采集开启且缓存为空
		end
	end

	// 设备整帧完成后只发布一个缓存写指令。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_rx_store <= 1'b0;              // 初始无整帧要写入
		end else begin
			flag_rx_store <= rx_complete & flag_rx_space; // 不是独立采样率发生器
		end
	end

	// 右字在移位器清空之前与入缓存命令一同暂存。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_rx_right <= 16'h0000;           // 右字暂存初始静默
		end else if(rx_complete == 1'b1)begin
			reg_rx_right <= rx_word;            // 保存包括边界LSB的完整右字
		end
	end

	// 周期仅按设备生成并成功放入缓存的帧前进。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			cnt_rx_period <= 8'h00;             // 录音新包从首帧起步
		end else begin
			case({i_control[1], flag_rx_store})
				2'b10:begin
					cnt_rx_period <= cnt_rx_period; // 没有整帧不改变包进度
				end
				2'b11:begin
					cnt_rx_period <= rx_increment[7:0]; // 显式截进位实现模256
				end
				default:begin
					cnt_rx_period <= 8'h00;     // 停止撤销未完成的录音包
				end
			endcase
		end
	end

	// 收尾标记与位序比较同步延迟一拍。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_rx_boundary <= 1'b0;           // 初始无声道收尾
		end else begin
			flag_rx_boundary <= (reg_rx_command == CMD_LEFT) | (reg_rx_command == CMD_RIGHT); // 左右两种收尾
		end
	end

	// 普通采样标记与收尾标记采用相同延迟。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_rx_shift <= 1'b0;              // 初始无普通位指令
		end else begin
			flag_rx_shift <= (reg_rx_command == CMD_SHIFT); // 区分普通位与边界
		end
	end

	// 首个锁定边界之前的任意半帧不参与几何验收。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_check_geometry <= 1'b0;        // 初始无先前完整帧
		end else begin
			flag_check_geometry <= flag_rx_locked; // 与前一拍指令锁定状态对齐
		end
	end

	// 收尾之前必须已有十五个非边界位。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_slot_early <= 1'b0;            // 初始不报LR提前
		end else begin
			flag_slot_early <= flag_rx_boundary & ~flag_last_bit & flag_check_geometry; // 缺位的LR边界被拒绝
		end
	end

	// 第十六个非边界位表示LR切换滞后。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_slot_late <= 1'b0;             // 初始不报LR滞后
		end else begin
			flag_slot_late <= flag_rx_shift & flag_last_bit & flag_check_geometry; // 多出的普通位被拒绝
		end
	end

	// 无位事件年龄饱和保持，不回绕成正常值。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			cnt_watchdog <= 16'h0000;           // 初始失钟年龄清空
		end else begin
			case({flag_monitor_enable, bit_edge, watchdog_full})
				3'b100:begin
					cnt_watchdog <= watchdog_increment[15:0]; // 未饱和且无边沿才加一
				end
				3'b101:begin
					cnt_watchdog <= cnt_watchdog; // 饱和之后保持最坏年龄
				end
				default:begin
					cnt_watchdog <= 16'h0000;   // 事件刷新或停机撤销年龄
				end
			endcase
		end
	end

	// 失钟比较寄存为单拍条件。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_timeout <= 1'b0;               // 初始无失钟超时
		end else begin
			flag_timeout <= (cnt_watchdog == 16'hffff); // 约655us没有位边沿
		end
	end

	// 仅消费点检查播放饥饿，空闲系统拍不会误报。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_underrun <= 1'b0;              // 初始尚未消费播放帧
		end else begin
			flag_underrun <= tx_consume & ~flag_tx_pending; // 左帧起点缺少预取负载
		end
	end

	// 保守拒绝整帧边界时仍未释放的录音缓存。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_overrun <= 1'b0;               // 初始没有录音拥塞
		end else begin
			flag_overrun <= rx_complete & m_axis_tvalid_o; // 不覆盖旧录音负载
		end
	end

	// 包尾只能在真实接受帧的同拍比较。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			flag_bad_packet <= 1'b0;            // 初始无DMA包尾异常
		end else begin
			flag_bad_packet <= tx_accept & (i_s_axis_tlast != flag_tx_last); // 验证256帧周期
		end
	end

	// 独立事件按位锁存，后续正常时钟不能自动清除错误。
	always@(posedge i_clk or negedge i_rstn)begin
		if(i_rstn == 1'b0)begin
			reg_fault <= 5'b00000;              // 清除复位前全部诊断历史
		end else if(flag_ack_errors == 1'b1)begin
			reg_fault <= 5'b00000;              // 停机后的显式错误确认
		end else begin
			reg_fault <= reg_fault | {flag_bad_packet, flag_overrun, flag_underrun, slot_error, flag_timeout}; // 保持每种独立错误位
		end
	end

endmodule
