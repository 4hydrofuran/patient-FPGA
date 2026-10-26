"""Standard A11 package entry; fresh authorization is never embedded."""
import argparse
from pathlib import Path
from prepare_compute_bundle import main

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    main(p.parse_args().out.resolve())
