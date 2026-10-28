"""Compare repaired physical T8 with preserved canonical T1 at all captured layers."""
import json,sys
from analyze_state import ROOT,compare
p=ROOT/sys.argv[1]
r=compare(ROOT/'eval/qwen35/a05/state-v2/chunk-256',p/'chunk-256')
with (p/'canonical-history-comparison.json').open('x') as f:json.dump(r,f,indent=2)
print(json.dumps({'passed':r['passed'],'max_logits':max(x['max_abs'] for x in r['logits'].values()),'state_failures':sum(not x['passed'] for x in r['state_arrays'].values())}))
assert r['passed']
