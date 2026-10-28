# Ubuntu 桌面入口（本机预备，暂不上板）

这个入口打开现有服务。使用 Chromium 时，单独显示一个 1024×600 的应用窗口，没有地址栏和标签栏。HTML 和 Python 接口继续复用，不必重写原生 GUI。Firefox 作为兼容选项，仍是普通独立浏览器窗口。

模型及网页服务仍按已确认的板端流程启动；点击快捷方式只打开界面，不创建、停止或切换模型进程，也不配置开机自启。

先把本目录放到 Ubuntu 的固定位置，再执行：

```sh
python3 install.py --url http://127.0.0.1:8000/
```

会生成当前用户的应用菜单项，并在可识别的桌面目录放一份。Ubuntu 若显示“允许启动”，右键该图标选择“允许启动”即可。保留本目录原位置，快捷方式使用绝对路径。

开发电脑无板验证用：

```sh
python3 install.py --output-dir /tmp/patient-desktop-preview
python3 launch.py --browser /path/to/chromium --print-command
```

`--output-dir` 不修改桌面或应用菜单；`--print-command` 不启动浏览器。最终在 Ubuntu 的窗口显示和触摸需后续再确认，本轮不复制此目录到板端。
