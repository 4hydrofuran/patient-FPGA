"""Isolated worker launcher. No board/native action without its explicit CLI gate."""
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from single_compute_worker import main
    raise SystemExit(main())
