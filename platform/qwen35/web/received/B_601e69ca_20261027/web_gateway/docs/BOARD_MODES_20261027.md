# 本轮板端流程与验收

日期：2026-10-27。CPU / FPGA 切换已上板通过，随后按用户要求关机。串口确认 `reboot: Power down`。

## 当前交付

前端主目录仍为 `/home/ubuntu/patient-web-demo-20261026/web_gateway`，本轮7个程序文件已与本机逐个核对 SHA256。CPU与FPGA使用同一病例、聊天模板、事实检查和评价管线；页面新增“推理”选择，每条回答标记其实际执行来源。生成过程中不能切换，完成一轮后可以继续当前会话。

PS集成目录为 `/var/lib/kv260-a12/web-modes-20261027-v2`。之前已调通的 `/var/lib/kv260-a12/web-multi-20261026-v1` 未覆盖。本轮第一版前端备份位于 `web-modes-20261027-v1/front-before`。桌面快捷方式未上传到板卡；源码随本次仓库更新提供。

## 一次正常流程的结果

同一场 SYN_CP_01 问诊中，连续三次问“每次疼痛持续多久？”，实际执行为：

| 顺序 | 模式 | 回答 | 耗时 |
|---|---|---|---|
| 1 | FPGA_REAL | 每次疼痛持续 10 分钟。 | 35.129秒 |
| 2 | CPU_REFERENCE | 每次疼痛持续 10 分钟。 | 79.175秒 |
| 3 | FPGA_REAL | 每次疼痛持续 10 分钟。 | 33.623秒 |

三次均为 `MODEL`，`model_called=true`，通过事实检查并发布。随后结束问诊，主任评价10/100；重复询问同一个持续时间话题仍只计10分。切换回FPGA复用了原已预热worker，模型请求数2；CPU独立执行1次。

这三次耗时包含正常问诊处理，不是严格性能基准。没有执行取消、故障注入或压力矩阵。本机3项正常接线测试通过，1024×600下检查了模式选择、继续提问、主任评价；模式与动作控件高度均为48 CSS像素。本轮未重新操作板端显示屏和触摸。

证据：[板端问诊记录](acceptance/backend-modes-board-20261027.json)、[部署与关机记录](BACKEND_MODES_VERIFICATION.json)。

## 下次开机如何使用

1. 通过串口进入板上已有的 `6.8.12-a10irq2` 内核。此次只做一次性启动，默认启动配置仍保持原样；直接正常开机可能仍是 `6.8.0-1036-xilinx`，不能直接运行现有FPGA入口。
2. 登录Ubuntu后，启动一份新的PS运行窗口：

   ```sh
   sudo python3 /home/ubuntu/patient-web-demo-20261026/run-modes.py
   ```

   此脚本从已经验收的v2模板复制一份新运行目录，重新建立本次窗口，保留旧记录。它补齐重启后消失的临时锁文件，并重新建立下述临时桌面规则。脚本已同步且检查了文件一致性；本轮已完成的模型验收由同样的模板与准备步骤启动，没有额外重跑该封装脚本。

3. 等待模型加载与一次预热完成。服务就绪后，在**板上的浏览器**打开 `http://127.0.0.1:8000/`。CPU模型按首次选择时加载；后续切回FPGA复用其预热状态。
4. 开始问诊 → 输入问题 → 等待回答 → 在两轮之间选择CPU或FPGA → 结束问诊 → 查看主任评价。当前后台运行窗口沿用原来的4小时上限和180秒单次回答预算。

需要一次性启动内核时，U-Boot中的已验证命令如下；不执行 `saveenv`：

```text
fatload mmc 1:1 0x10000000 a10-candidate-irq2-20261021.fit
setenv bootargs root=LABEL=writable rootwait earlycon console=ttyPS1,115200 console=tty1 clk_ignore_unused uio_pdrv_genirq.of_id=generic-uio xilinx_tsn_ep.st_pcp=4 cma=800M
bootm 0x10000000#conf-smk-k26-revA-sck-kv-g-revB
```

网页仍只监听板上回环地址；电脑自己的127.0.0.1并不是板子。网线实际可达192.168.137.2，本轮未重新配置网络、SSH密钥或默认启动项。

## 本次开机适配和收尾

重启后 `/run/lock/patient-qwen-linear.lock` 不存在，已按原PS接口补建。首次加载时，GDM登录界面占用了加速器DRM设备；该次窗口在模型进程启动前停止，没有提交计算，已释放并恢复默认PL，记录明确为启动失败收尾，未声称模型正常退出。

之后添加本次启动有效的 `/run/udev/rules.d/71-patient-zocl-display.rules`：

```text
SUBSYSTEM=="drm", DRIVERS=="zocl-drm", TAG+="mutter-device-ignore"
```

它让GNOME跳过加速器作为显示设备，PS显示设备继续由桌面使用；此行为依据 [GNOME Mutter 的设备忽略逻辑](https://raw.githubusercontent.com/GNOME/mutter/gnome-46/src/backends/native/meta-udev.c)。规则在重启后消失，由启动脚本重建。本轮验收时GDM保持运行，未放宽原PS硬件检查。

验收结束后，先向新窗口写入正常停止请求。PS worker正常退出0、卸载测试PL、恢复默认PL并归档lease。确认无活动lease、zocl已卸载后，结束只保留历史结果的网页进程，执行 `systemctl poweroff`，串口确认关机。原内核文件、默认启动配置、模型权重未改写。

## 桌面快捷方式进度

`desktop-preview/` 包含桌面入口生成脚本、启动器和图标，优先使用Chromium独立应用窗口。已在电脑验证文件格式、含空格的路径和启动参数，未启动模型。本机WSL由于E盘路径不可用，未进行Ubuntu实际图形窗口验证；未上传或安装到板子。
