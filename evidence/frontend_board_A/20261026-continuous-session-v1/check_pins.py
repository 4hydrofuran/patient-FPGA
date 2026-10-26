import json
from pathlib import Path
out=Path(__file__).parent
r=json.loads((out/'setup-uart.json').read_text(encoding='utf-8-sig'));assert r['error'] is None
installed=json.loads(r['output'].rsplit('__PL_BEGIN__',1)[1].split('__PL_END__')[0])
p=json.loads((out.parents[1]/'model_pl_A/20261026-pl-authfix-board-v2/TESTED_SOURCE_PINS.json').read_text())
expected=dict(p['tested_sources'],**{'bin/qwen35-a12':p['native_binary_sha256']})
assert installed['base_pins']==expected
(out/'PIN_MATCH.json').write_text(json.dumps(dict(status='EXACT_MATCH_OPTIMIZED_BINARY_AND_MANAGEMENT_SOURCES',actual=installed['base_pins'],root=installed['root']),indent=2))
print('OPTIMIZED_SOURCE_AND_BINARY_MATCH')
