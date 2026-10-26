import json
from pathlib import Path
r={}
for base in (Path('/sys/kernel/debug/cma'),Path('/sys/kernel/mm/cma')):
    if base.exists():
        for p in base.glob('*/*'):
            if p.name in ('base_pfn','count','used','maxchunk','order_per_bit'):
                try:r[str(p)]=p.read_text()[:500]
                except OSError:pass
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
