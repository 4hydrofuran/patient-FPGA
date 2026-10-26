"""Isolated manager launcher; does not import native worker or XRT."""
from pathlib import Path
import sys
if __name__=='__main__':
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from mlp_manager import main
    raise SystemExit(main())
