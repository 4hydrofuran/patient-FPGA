import json
from pathlib import Path
r={}
for name in ('/sys/kernel/debug/dri/0/framebuffer','/sys/kernel/debug/dri/0/gem_names','/sys/kernel/debug/dma_buf/bufinfo'):
    p=Path(name)
    if p.exists():r[name]=p.read_text()[-14000:]
r['memory']={l.split(':')[0]:l.split(':')[1].strip() for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith(('MemAvailable:','CmaFree:','CmaTotal:','Cached:'))}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
