import json,sys
from pathlib import Path
sys.path.insert(0,'/var/lib/kv260-a12/manual-web-20261026-v2/bundle/control/support')
from accelerator_release_gate_v2 import collect
r=collect(allow_ps_display=True)
print('__PL_BEGIN__');print(json.dumps(dict(device_holders=r['device_holders'],device_mappings=r['device_mappings'],refcount=Path('/sys/module/zocl/refcnt').read_text())));print('__PL_END__')
