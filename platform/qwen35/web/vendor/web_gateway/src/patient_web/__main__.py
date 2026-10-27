"""Explicit startup mode; default native never silently becomes a demonstration."""

import argparse
from pathlib import Path

import uvicorn

from .api import create_app


def main():
    parser = argparse.ArgumentParser(description="KV260 文字接口和状态事件服务")
    parser.add_argument("--backend", choices=("native", "demo"), default="native")
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--threads", type=int, choices=(2, 3), default=3)
    parser.add_argument("--demo-lab", action="store_true", help="Enable explicit no-model fault scenarios at /lab")
    parser.add_argument("--generation-timeout", type=float, default=180,
                        help="Per-answer model budget, 1..600 seconds (default: 180)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be in 1..65535")
    if args.demo_lab and args.backend != "demo":
        parser.error("--demo-lab requires --backend demo")
    if not 1 <= args.generation_timeout <= 600:
        parser.error("--generation-timeout must be in 1..600")
    # One process, one persistent model, same loopback origin for console/API/SSE.
    uvicorn.run(create_app(backend=args.backend, project_root=args.project_root,
                           output=args.output, threads=args.threads, demo_lab=args.demo_lab,
                           generation_timeout_s=args.generation_timeout),
                host="127.0.0.1", port=args.port, workers=1)


if __name__ == "__main__":
    main()

