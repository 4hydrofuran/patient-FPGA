"""Actual full-model teacher forcing, R0, cancellation and chunk experiments.
Predeclared diagnostic tolerance from A01: 0.002 + 0.0002*abs(reference).
Chunk differences are failures, not silently relabeled as quantization quality.
"""
import argparse,hashlib,json,sys
from pathlib import Path
from native_client import ROOT,Worker
sys.path.insert(0,str(ROOT/'runtime/qwen35_cpu'))
from test_baseline import render
def save(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--binary',default='/home/member-a/qwen35-a05/build-v3/qwen35-s1');a=ap.parse_args();out=ROOT/a.output;out.mkdir(exist_ok=False)
    save(out/'acceptance.json',{'fixed_inputs':'short teacher-forced prompt and same forced tokens across schedules','atol':.002,'rtol':.0002,'operator_atol':.0001,'operator_rtol':.00001,'r0_required':'bit-exact logits and tokens','R1':'OPTIONAL_DISABLED','BOARD':'NOT_TESTED'})
    sources=list((ROOT/'runtime/qwen35_w4a8').glob('*'))+[Path(__file__)]
    save(out/'source_hashes.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.is_file()})
    prompt=render([{'role':'user','content':'只回答数字：2加3等于多少？'}]);records={};checks=[]
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    w=Worker(out/'worker',binary=a.binary);save(out/'ready.json',w.ready);save(out/'argv.json',w.argv)
    try:
        tokens=w.call({'id':'tokenize','op':'tokenize','prompt':prompt})['tokens']
        teacher=[20,151645] # fixed vocab IDs used only as teacher input, not expected greedy output
        save(out/'inputs.json',{'tokens':tokens,'teacher':teacher,'prompt':prompt})
        for chunk in (256,1,2,4,8):
            name='chunk-'+str(chunk);r=w.call({'id':name,'tokens':tokens,'max_tokens':len(teacher),'teacher_tokens':teacher,'prefill_chunk':chunk,'logits_mode':'all','diagnostic_dir':str(out/name),'diagnostic_all_layers':chunk==256,'dump_state':True})
            records[name]=r;check(name+' real-72-and-clear',r.get('status')=='OK' and len(r['bridge']['weights'])==72 and all(x['calls'] for x in r['bridge']['weights'].values()) and r['state_position_after_clear']==-1)
            print(json.dumps({'step':name,'status':r.get('status'),'prefill_ms':r.get('prefill_ms')}),flush=True)
        base={'prompt':prompt,'max_tokens':8}
        a0=w.call({'id':'baseline',**base});records['baseline']=a0
        r=w.call({'id':'followup','prompt':render([{'role':'user','content':'哪里痛？'},{'role':'assistant','content':'胸骨后。'},{'role':'user','content':'持续多久？'}]),'max_tokens':8});records['followup']=r
        r=w.call({'id':'cancel-real','tokens':tokens,'max_tokens':64},cancel_at_token=True);records['cancel']=r;check('actual-SIGUSR1-CANCELLED-clear',r.get('status')=='CANCELLED' and r['state_position_after_clear']==-1)
        for name,req in [('after-cancel',base),('after-unplayed',base)]:
            r=w.call({'id':name,**req});records[name]=r;check(name+' exact',r.get('status')=='OK' and r['output_tokens']==a0['output_tokens'] and r['last_prompt_logits_fnv64']==a0['last_prompt_logits_fnv64'])
        check('R1 explicit reject',w.call({'id':'R1','cache_policy':'R1',**base})['type']=='error')
        check('reset ack',w.call({'id':'reset','op':'reset'})['type']=='reset')
        r=w.call({'id':'after-reset',**base});records['after-reset']=r;check('reset exact',r.get('last_prompt_logits_fnv64')==a0['last_prompt_logits_fnv64'])
        r=w.call({'id':'other-case','prompt':render([{'role':'user','content':'我是另一个合成病例，只回答：右侧胸部。'}]),'max_tokens':12});records['other-case']=r
        r=w.call({'id':'after-case',**base});records['after-case']=r;check('case-prefix invalidated exact',r.get('last_prompt_logits_fnv64')==a0['last_prompt_logits_fnv64'])
        # Real long prefill, final-logits only. Context stays bounded and valid.
        for length in (256,1024):
            r=w.call({'id':'long-'+str(length),'tokens':(tokens*((length+len(tokens)-1)//len(tokens)))[:length],'max_tokens':1,'teacher_tokens':[20]});records['long-'+str(length)]=r
            check('long-'+str(length)+' complete',r.get('status')=='OK' and r['prompt_tokens']==length and r['prefill_requested_logits']==1)
            print(json.dumps({'step':'long-'+str(length),'prefill_ms':r.get('prefill_ms'),'status':r.get('status')}),flush=True)
        check('one weight load only',records['long-1024']['bridge']['weight_load_count']==72)
        check('protected original MLP pages no RSS',records['long-1024']['bridge']['protected_gguf_rss_kib']==0)
        check('cache reuse real',records['long-1024']['bridge']['gate_up_cache_hits']>0)
    finally:w.close();save(out/'records.json',records);save(out/'checks.json',checks)
    # Same graph/input scalar vs optimized; CPU quality not conflated with quantization.
    w=Worker(out/'scalar-worker',algorithm='SCALAR',kernel_threads=1,binary=a.binary)
    try:
        r=w.call({'id':'scalar','tokens':tokens,'max_tokens':len(teacher),'teacher_tokens':teacher,'logits_mode':'all','diagnostic_dir':str(out/'scalar'),'diagnostic_all_layers':True,'dump_state':True},seconds=240);save(out/'scalar-result.json',r)
    finally:w.close()
    print(json.dumps({'functional_checks':len(checks),'passed':all(x['passed'] for x in checks),'numerics':'PENDING_ANALYSIS'}));return int(not all(x['passed'] for x in checks))
if __name__=='__main__':raise SystemExit(main())
