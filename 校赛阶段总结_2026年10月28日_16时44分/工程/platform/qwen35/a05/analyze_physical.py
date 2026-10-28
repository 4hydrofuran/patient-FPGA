import json,sys
from analyze_state import compare,ROOT
p=ROOT/sys.argv[1]
result={str(t):compare(p/'chunk-1',p/f'chunk-{t}') for t in (2,4,8,256)}
hist={str(t):{} for t in (1,2,4,8,256)}
for t,counts in hist.items():
    m=json.loads((p/f'chunk-{t}'/'manifest.json').read_text())
    for x in m['projections']:counts[str(x['T'])]=counts.get(str(x['T']),0)+1
with (p/'physical-numerics.json').open('x') as f:json.dump({'comparisons':result,'actual_MLP_T_histogram':hist},f,indent=2)
summary={t:{'passed':v['passed'],'max_logits':max(x['max_abs'] for x in v['logits'].values()),'state_failed':sum(not x['passed'] for x in v['state_arrays'].values())} for t,v in result.items()}
print(json.dumps({'summary':summary,'actual_MLP_T_histogram':hist}))
assert all(v['passed'] for v in result.values())
assert all(str(t) in hist[str(t)] for t in (2,4,8))
