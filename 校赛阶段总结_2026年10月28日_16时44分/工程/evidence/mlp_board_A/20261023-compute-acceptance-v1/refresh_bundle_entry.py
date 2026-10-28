"""Keep the standard packaging entry consistent with the reviewed compute path."""
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=E.parents[2]
p=ROOT/'platform/qwen35/a11/prepare_bundle.py'
with (E/'source_before/prepare_bundle.py').open('xb') as f:f.write(p.read_bytes())
p.write_text('''"""Standard A11 package entry; fresh authorization is never embedded."""
import argparse
from pathlib import Path
from prepare_compute_bundle import main

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    main(p.parse_args().out.resolve())
''',encoding='utf-8')
print(p)
