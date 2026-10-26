# HDMI 图形输出恢复与真实结果预览

用户要求启用图形服务并在HDMI屏幕看结果。已确认没有活动PL租约，GDM本来active，但只有gdm登录会话。用户多次报告屏幕无背光/无信号，确认独立电源、触控USB及板载HDMI直连，屏幕接电脑工作正常、早期默认系统可显示。

操作及实测：先start gdm、activate c3，登录画面未出现。读取显示状态发现DPMS Off、CRTC active=0、EDID长度0、640×480备用模式。经GDM会话的Mutter运行时电源切换、临时800×600模式和一次临时uinput Shift按下/释放，实际扫描变为active=1；用户仍无画面。随后读取到有效256字节EDID（两段checksum=0）、首选1024×600，重探测connector；不能仅凭这些时间相邻动作推定EDID恢复的唯一根因。

之后检测到用户已经登录ubuntu图形会话14/tty2，原GDM会话退出，GNOME扫描自动采用1024×600。未代用户输入凭据、未开启自动登录。原向gdm会话应用原生分辨率的调用因会话已消失返回D-Bus错误；未因此改认证或系统配置。最终原生1024×600、CRTC active=1、DPMS On有实读。未重启、未刷写、未变更PL或重新跑模型。

已将刚才真实PL运行的问答、评价截图及真实文字回执准备为 `/home/ubuntu/snap/firefox/common/pl-result-20261026-v1/index.html`。页面明确标注这是已完成的MODEL/FPGA_REAL记录，当前没有重新推理，不是在线问答服务。以ubuntu运行全屏Firefox及临时idle inhibitor，profile为 `hdmi-preview-20261026-v1`，启动PID7864仍运行。使用实际gsd-power进程的DISPLAY/WAYLAND_DISPLAY/XAUTHORITY/用户DBus会话环境；首次读取gnome-shell初始环境缺DISPLAY而启动exit1，修正后运行成功。未修改持久息屏/安全配置。

当前最后一步等待用户确认HDMI上实际看见结果页面；不能仅凭进程活着声称物理屏幕已验证。串口操作已释放，图形浏览器为用户请求保留运行。根本问题/重复稳定性尚未定论，不将无头浏览器证据冒称此前HDMI可用。

最新完成确认：用户在本聊天明确回复“已看到结果页面”。HDMI物理屏幕显示此次真实PL记录的基本功能现已得到用户确认，当前桌面与全屏浏览器保留运行。以上“等待确认”是历史过程，不代表仍待确认。未新增推理或常驻模型服务，未测试物理触控交互。

证据在 `evidence/frontend_board_A/20261026-board-integration-v1/` 的 display-*/wake-*/reprobe-*/open-hdmi-result* 回执。准备结果页首轮Unicode转义笔误导致脚本编译拒绝，原失败保留，修正后未重跑推理；另一次本机PowerShell生成临时脚本引号错误在板端执行前拒绝，随后改用独立脚本。
