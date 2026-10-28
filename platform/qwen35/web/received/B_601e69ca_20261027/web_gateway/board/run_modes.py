"""Start a fresh window from the board's already integrated PS template."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description="启动已集成 CPU/FPGA 切换的板端问诊服务")
    parser.add_argument("--template", type=Path,
                        default=Path("/var/lib/kv260-a12/web-modes-20261027-v2"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, "请使用 sudo python3 run_modes.py 启动。\n")
    if os.uname().release != "6.8.12-a10irq2":
        parser.exit(1, "请先按已确认的方法临时启动 6.8.12-a10irq2 内核。\n")
    if Path("/var/lock/kv260-a1/active").exists():
        parser.exit(1, "已有 PS 运行窗口；如问诊服务已就绪，直接打开 http://127.0.0.1:8000/ 。\n")
    template = args.template.resolve()
    if not (template / "web_managed.py").is_file():
        parser.exit(1, "尚未找到板上已集成的模式切换模板。\n")
    lock = Path("/run/lock/patient-qwen-linear.lock")
    if not lock.exists():
        with lock.open("x"):
            pass
        lock.chmod(0o600)
    rule = Path("/run/udev/rules.d/71-patient-zocl-display.rules")
    rule.write_text('SUBSYSTEM=="drm", DRIVERS=="zocl-drm", TAG+="mutter-device-ignore"\n')
    subprocess.run(["udevadm", "control", "--reload-rules"], check=True)
    window = "a12-web-modes-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    root = template.parent / window.removeprefix("a12-")
    root.mkdir(mode=0o700)
    for path in template.glob("*.py"):
        shutil.copy2(path, root / path.name)
    shutil.copy2(template / "web-config.json", root / "web-config.json")
    shutil.copytree(template / "bundle", root / "bundle",
                    ignore=shutil.ignore_patterns("run-v1*", "__pycache__"))
    spec_path = root / "bundle/control/window-spec.json"
    spec = json.loads(spec_path.read_text())
    spec["window_id"] = window
    spec_path.write_text(json.dumps(spec, indent=2))
    with (root / "manager.stdout").open("xb") as out, (root / "manager.stderr").open("xb") as err:
        process = subprocess.Popen([
            "/usr/bin/python3", "-B", "-I", str(root / "interactive_entry.py")
        ], stdout=out, stderr=err, start_new_session=True)
    (root / "started.json").write_text(json.dumps({"pid": process.pid}))
    print(f"服务正在启动，PID {process.pid}；日志：{root}/manager.stderr")
    print("模型预热就绪后，在板上打开 http://127.0.0.1:8000/ 。")


if __name__ == "__main__":
    main()
