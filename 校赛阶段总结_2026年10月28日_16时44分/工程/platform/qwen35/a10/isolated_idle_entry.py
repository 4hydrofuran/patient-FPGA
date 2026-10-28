"""Worker launcher for python -I; only its pinned package directory is added."""
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from isolated_idle_worker import main
    raise SystemExit(main())
