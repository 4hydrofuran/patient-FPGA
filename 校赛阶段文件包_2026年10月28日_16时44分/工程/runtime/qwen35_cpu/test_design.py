"""A-DESIGN-1.0 native diagnostics; no board and no public ABI changes.

Predeclared FP all-position GEMM vs selected-position GEMV logits tolerance:
abs <= 0.002 + 0.0002*abs(reference), entire 248320 vocabulary, not W4A8 tolerance.
Legacy/final matching additionally requires exact hash and generated tokens.
Small diagnostic samples only: no p95, quality, or production speedup claim.
"""
import argparse
import json
from pathlib import Path
from test_baseline import Native, render

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--binary',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    results=[];failures=[]
    def check(ok,label):
        if not ok:failures.append(label)
    n=Native(a.binary,a.model,a.output,'compare')
    try:
        check(n.ready['n_seq_max']==1 and n.ready['n_rs_seq']==0,'one slot no snapshot')
        prompt=render([{'role':'user','content':'只回答数字：2加3等于多少？'}])
        base=n.request({'op':'tokenize','prompt':prompt})['tokens']
        pad=n.request({'op':'tokenize','prompt':'资料'})['tokens'][-1]
        for length in (256,1024,2048):
            tokens=base[:3]+[pad]*(length-len(base))+base[3:]
            pair=[]
            for mode in ('legacy_chunk_last','final'):
                r=n.request({'id':f'{length}-{mode}','tokens':tokens,'max_tokens':8,'logits_mode':mode,
                             'save_logits_reference':mode=='legacy_chunk_last','compare_logits':mode=='final'})
                results.append(r);pair.append(r)
                check(r.get('status')=='OK',r['id'])
                check(r['prefill_requested_logits']==(length//256 if mode=='legacy_chunk_last' else 1),'requested rows '+r['id'])
            check(pair[0]['last_prompt_logits_fnv64']==pair[1]['last_prompt_logits_fnv64'],'exact final logits '+str(length))
            check(pair[0]['output_tokens']==pair[1]['output_tokens'],'exact generated tokens '+str(length))
            check(pair[1]['logits_comparison']['failures']==0,'all vocabulary comparison '+str(length))
        # Test full output positions at the bound; retain logs even if comparison fails.
        tokens=base[:3]+[pad]*(256-len(base))+base[3:]
        selected=n.request({'id':'full-reference','tokens':tokens,'max_tokens':8,'save_logits_reference':True});results.append(selected)
        allrows=n.request({'id':'all-256','tokens':tokens,'max_tokens':8,'logits_mode':'all','compare_logits':True});results.append(allrows)
        check(allrows['prefill_requested_logits']==256,'all diagnostic rows')
        check(allrows['logits_comparison']['failures']==0,'full vs selected all vocabulary tolerance')
        check(allrows['output_tokens']==selected['output_tokens'],'full vs selected generation')
        for req in ({'logits_mode':'invalid','tokens':base},{'logits_mode':'all','tokens':tokens+[pad]}):
            r=n.request(dict(req,max_tokens=1));results.append(r);check(r['type']=='error','reject invalid diagnostic')
    finally:n.close()
    # Same long-answer input with/without profiling; instrumented result kept separate.
    long_prompt=render([{'role':'user','content':'用约80个汉字描述一间安静的图书馆，不要列举要点。'}])
    normal=Native(a.binary,a.model,a.output,'normal-profile-control')
    try:
        control=normal.request({'id':'normal-control','prompt':long_prompt,'max_tokens':32});results.append(control)
    finally:normal.close()
    instrumented=Native(a.binary,a.model,a.output,'instrumented',profile=True)
    try:
        trace=instrumented.request({'id':'profile','prompt':long_prompt,'max_tokens':32});results.append(trace)
        check(trace['status']=='OK' and trace['decode_calls']>=8,'real decode profile')
        check(trace['output_tokens']==control['output_tokens'],'instrumentation tokens')
        check(trace['last_prompt_logits_fnv64']==control['last_prompt_logits_fnv64'],'instrumentation logits')
        head=[v for k,v in trace['node_profile'].items() if k.startswith('prefill|result_output|')]
        check(len(head)==1 and head[0]['output_rows']==1,'actual head output row')
        # Observe zero-output intermediate chunks in the backend, not just host flags.
        pruned=instrumented.request({'id':'profile-pruned-1024','tokens':base[:3]+[pad]*(1024-len(base))+base[3:], 'max_tokens':2})
        results.append(pruned)
        head=[v for k,v in pruned['node_profile'].items() if k.startswith('prefill|result_output|')]
        check(len(head)==1 and head[0]['output_rows']==1,'actual head total rows across chunks')
    finally:instrumented.close()
    report={'status':'FAIL' if failures else 'PASS','domain':'PC','BOARD':'NOT_TESTED','failures':failures,
            'model':str(a.model),'ready':n.ready,'results':results,
            'tolerance':{'scope':'F16/Q4 selected vs full logits, NOT W4A8','atol':0.002,'rtol':0.0002},
            'performance_scope':'Single diagnostic samples. Node fences inhibit fusion and add overhead; not throughput/board acceptance.'}
    (a.output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'failures':failures,'output':str(a.output)}))
    return bool(failures)

if __name__=='__main__':raise SystemExit(main())
