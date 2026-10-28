"""Final build identity, no diagnostic I/O, chunk equivalence and R0 recovery."""
import json,sys
from native_client import ROOT,Worker
out=ROOT/sys.argv[1];out.mkdir(exist_ok=False);inp=json.loads((ROOT/'eval/qwen35/a05/state-v2/inputs.json').read_text())
w=Worker(out/'worker');rows=[];checks=[]
try:
    def request(name,chunk,**extra):return w.call({'id':name,'tokens':inp['tokens'],'teacher_tokens':inp['teacher'],'max_tokens':len(inp['teacher']),'prefill_chunk':chunk,**extra})
    first=request('whole',256,save_logits_reference=True);rows.append(first)
    for t in (1,2,4,8):
        r=request('chunk'+str(t),t,compare_logits=True);rows.append(r);checks.append(r['logits_comparison']['max_abs']==0 and r['output_tokens']==first['output_tokens'])
    cancelled=w.call({'id':'cancel','tokens':inp['tokens'],'max_tokens':64},cancel_at_token=True);rows.append(cancelled);checks.append(cancelled['status']=='CANCELLED')
    r=request('recover',256,compare_logits=True);rows.append(r);checks.append(r['logits_comparison']['max_abs']==0)
    checks+= [all(x['calls']>0 for x in r['bridge']['weights'].values()),r['bridge']['protected_gguf_rss_kib']==0,r['bridge']['weight_load_count']==72,r['state_position_after_clear']==-1,w.ready['physical_ubatch']==1]
finally:w.close()
with (out/'summary.json').open('x') as f:json.dump({'passed':all(checks),'checks':len(checks),'ready':w.ready,'rows':rows,'physical_ubatch':1,'performance_mode':'final logits only, no tensor dumps','BOARD':'NOT_TESTED'},f,indent=2)
print(json.dumps({'passed':all(checks),'checks':len(checks)}));raise SystemExit(not all(checks))
