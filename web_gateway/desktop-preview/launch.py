"""Open the existing local consultation service in an Ubuntu application window."""

import argparse
import json
import shutil
import subprocess


def browser_command(url, browser=None):
    candidates = [browser] if browser else [
        "chromium", "chromium-browser", "google-chrome", "firefox"
    ]
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            if "firefox" in executable.lower():
                return [executable, "--new-window", url]
            return [executable, "--app=" + url, "--window-size=1024,600"]
    raise RuntimeError("未找到浏览器。请安装 Chromium，或使用 --browser 指定已安装的浏览器。")


def main():
    parser = argparse.ArgumentParser(description="打开问诊训练桌面窗口，不启动或重启模型")
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--browser", help="已有 Chromium/Chrome/Firefox 的命令名或路径")
    parser.add_argument("--print-command", action="store_true", help="仅显示启动参数，用于无板验证")
    args = parser.parse_args()
    try:
        command = browser_command(args.url, args.browser)
    except RuntimeError as error:
        parser.exit(1, str(error) + "\n")
    if args.print_command:
        print(json.dumps(command, ensure_ascii=False))
    else:
        subprocess.Popen(command, start_new_session=True)


if __name__ == "__main__":
    main()
