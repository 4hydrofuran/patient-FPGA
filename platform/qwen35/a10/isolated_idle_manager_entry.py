"""Manager launcher for python -I; never imports the native XRT worker."""
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from isolated_idle_trial import main
    raise SystemExit(main())
