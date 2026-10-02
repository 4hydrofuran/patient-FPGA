import subprocess
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable


def start_backend():
    backend_dir = PROJECT_DIR / "backend"
    print("正在启动后端: http://127.0.0.1:8000", flush=True)
    return subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "backend_api:app"],
        cwd=backend_dir,
    )


def start_frontend():
    frontend_dir = PROJECT_DIR / "frontend"
    print("正在启动前端: http://127.0.0.1:8501", flush=True)
    return subprocess.Popen(
        [
            PYTHON,
            "-m",
            "streamlit",
            "run",
            "frontend.py",
            "--server.port=8501",
            "--server.address=0.0.0.0",
        ],
        cwd=frontend_dir,
    )


def stop_process(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    backend_process = start_backend()
    time.sleep(3)

    if backend_process.poll() is not None:
        print(f"后端启动失败，退出码: {backend_process.returncode}", file=sys.stderr)
        sys.exit(1)

    frontend_process = start_frontend()
    time.sleep(3)

    if frontend_process.poll() is not None:
        print(f"前端启动失败，退出码: {frontend_process.returncode}", file=sys.stderr)
        stop_process(backend_process)
        sys.exit(1)

    print("服务已启动。前端地址: http://127.0.0.1:8501", flush=True)

    try:
        while True:
            if backend_process.poll() is not None:
                print(f"后端进程已退出，退出码: {backend_process.returncode}", file=sys.stderr)
                stop_process(frontend_process)
                sys.exit(backend_process.returncode or 1)
            if frontend_process.poll() is not None:
                print(f"前端进程已退出，退出码: {frontend_process.returncode}", file=sys.stderr)
                stop_process(backend_process)
                sys.exit(frontend_process.returncode or 1)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        stop_process(frontend_process)
        stop_process(backend_process)
