"""Install a per-user desktop entry; --output-dir makes a review-only preview."""

import argparse
import os
from pathlib import Path
import shutil
import sys


def desktop_arg(value):
    # Desktop Entry Exec escaping differs from shell quoting.
    value = str(value).replace("%", "%%")
    for char in ("\\", '"', "`", "$"):
        value = value.replace(char, "\\" + char)
    return '"' + value + '"'


def main():
    parser = argparse.ArgumentParser(description="准备问诊训练桌面快捷方式")
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--browser")
    parser.add_argument("--output-dir", type=Path,
                        help="只写到指定目录，不安装到桌面或应用菜单")
    args = parser.parse_args()
    if args.output_dir:
        destination = args.output_dir.resolve()
    else:
        destination = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
    destination.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parent
    command = [sys.executable, source / "launch.py", "--url", args.url]
    if args.browser:
        command += ["--browser", args.browser]
    entry = destination / "patient-consultation.desktop"
    entry.write_text("\n".join([
        "[Desktop Entry]", "Version=1.0", "Type=Application",
        "Name=问诊训练", "Comment=打开本机问诊与主任评阅界面",
        "Exec=" + " ".join(desktop_arg(part) for part in command),
        "Icon=" + str(source / "icon.svg"), "Terminal=false",
        "Categories=Education;", "StartupNotify=true", "",
    ]), encoding="utf-8")
    entry.chmod(0o755)
    print(entry)
    if not args.output_dir:
        import subprocess
        finder = shutil.which("xdg-user-dir")
        if finder:
            desktop = Path(subprocess.check_output([finder, "DESKTOP"], text=True).strip())
            if desktop.is_dir() and desktop != Path.home():
                copy = desktop / entry.name
                shutil.copy2(entry, copy)
                print(copy)


if __name__ == "__main__":
    main()
