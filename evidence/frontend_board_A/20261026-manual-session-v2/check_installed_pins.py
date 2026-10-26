import json,sys
from pathlib import Path
out=Path(__file__).parent
receipt=json.loads((out/(sys.argv[1] if len(sys.argv)>1 else 'setup02-uart.json')).read_text(encoding='utf-8-sig'));assert receipt['error'] is None
installed=json.loads(receipt['output'].rsplit('__PL_BEGIN__',1)[1].split('__PL_END__')[0])
pins=json.loads((out.parents[1]/'model_pl_A/20261026-pl-authfix-board-v2/TESTED_SOURCE_PINS.json').read_text())
expected=dict(pins['tested_sources'],**{'bin/qwen35-a12':pins['native_binary_sha256']})
assert installed['tested_base_pins']==expected
(out/('PIN_MATCH_LATEST.json' if len(sys.argv)>1 else 'PIN_MATCH.json')).write_text(json.dumps(dict(status='EXACT_MATCH_TESTED_OPTIMIZED_BASE',root=installed['root'],expected=expected,actual=installed['tested_base_pins']),indent=2))
print('EXACT_MATCH_TESTED_OPTIMIZED_BASE')
