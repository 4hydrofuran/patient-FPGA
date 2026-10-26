# A13 FAST PREBOARD

板前实现与针对核验完成；未连接/部署/执行板卡，BOARD=NOT_TESTED。
交接：`docs/handoffs/A_A13_FAST_PREBOARD_COMPLETE_20261026.md`。

交付为native1036五模块、两份分层DT、封存PL位流和全零PCM程序；9项资产、25份打包文件。
5模块/136项CRC、原生启动FIT DTB合并、8项针对PC生命周期检查均通过。
正常/异常路径不热回载、不强卸载、不重启；完成后保留音频配置/实际维护所有权。
默认入口已实际验证PLAN_ONLY；模板未授权、boot/log=null。

所有命令及退出码见本目录*.json；SHA/长度见PACKAGE.json与candidate-01/MANIFEST.json。
初次GPL字符串误拒和旧v2固件路径错误原失败保留，修订后abi-02/dt-02通过。
GCC13.4/13.3差异和BTF未生成诊断保留。未改四旧模块源/RTL及启动/默认平台原件，
未重建SDK或重跑无关仿真/CDC/STA。真实IIC/DMA/供电/声学尚未测；不保证绝不卡死。
